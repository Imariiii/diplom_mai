-- Sakila OLTP validation — зеркало SAKILA_OLTP_TRANSACTIONS (веса 40/35/25)
-- Команды: только run (prepare/cleanup не нужны — данные уже в Sakila/Pagila)

if sysbench.cmdline.command == nil then
    error("Укажите команду: run")
 end
 
 if sysbench.cmdline.command ~= "run" then
    if sysbench.cmdline.command == "help" then
       print("Использование: sysbench sakila_oltp_validation.lua --threads=N --events=M run")
       print("Перед замером: прогон --time=5 run (warmup)")
    end
    return
 end
 
 sysbench.cmdline.options = {
    id_sample_limit = {"Сколько PK сэмплировать (как в backend LIMIT 1000)", 1000},
 }
 
 local function rand_order_clause(drv_name)
    if drv_name == "pgsql" then
       return "ORDER BY random()"
    end
    return "ORDER BY RAND()"
 end
 
 local function load_id_pool(con, drv_name, table_name, column_name, limit)
    local order_clause = rand_order_clause(drv_name)
    local sql = string.format(
       "SELECT %s FROM %s WHERE %s IS NOT NULL %s LIMIT %d",
       column_name, table_name, column_name, order_clause, limit
    )
    local rs = con:query(sql)
    local pool = {}
    for i = 1, rs.nrows do
       local row = rs:fetch_row()
       pool[i] = tonumber(row[1]) or row[1]
    end
    if #pool == 0 then
       error(string.format("Пустой пул ID: %s.%s", table_name, column_name))
    end
    return pool
 end
 
 local function pick(pool)
    return pool[math.random(#pool)]
 end
 
 -- Пулы PK (кэш на поток)
 local film_ids, customer_ids, rental_ids
 
 function thread_init()
    drv = sysbench.sql.driver()
    con = drv:connect()
    math.randomseed(os.time() + sysbench.tid)
 
    local lim = sysbench.opt.id_sample_limit
    film_ids = load_id_pool(con, drv:name(), "film", "film_id", lim)
    customer_ids = load_id_pool(con, drv:name(), "customer", "customer_id", lim)
    rental_ids = load_id_pool(con, drv:name(), "rental", "rental_id", lim)
 
    -- Мешок весов 40 + 35 + 25 = 100 (как weighted_units в LoadTester)
    tx_bag = {}
    for _ = 1, 40 do table.insert(tx_bag, 1) end
    for _ = 1, 35 do table.insert(tx_bag, 2) end
    for _ = 1, 25 do table.insert(tx_bag, 3) end
 end
 
 function thread_done()
    con:disconnect()
 end
 
 local function tx_film_availability()
    local fid = pick(film_ids)
    con:query(string.format(
       "SELECT film_id, title, rental_rate FROM film WHERE film_id = %s", fid))
    con:query(string.format(
       "SELECT inventory_id, film_id, store_id FROM inventory WHERE film_id = %s LIMIT 5", fid))
 end
 
 local function tx_customer_touch()
    local cid = pick(customer_ids)
    con:query(string.format(
       "SELECT customer_id, first_name, last_name, active FROM customer WHERE customer_id = %s", cid))
    con:query(string.format(
       "UPDATE customer SET last_update = NOW() WHERE customer_id = %s", cid))
 end
 
 local function tx_rental_touch()
    local rid = pick(rental_ids)
    con:query(string.format(
       "SELECT rental_id, inventory_id, customer_id, rental_date FROM rental WHERE rental_id = %s", rid))
    con:query(string.format(
       "SELECT inventory_id, film_id, store_id FROM inventory WHERE inventory_id = (SELECT inventory_id FROM rental WHERE rental_id = %s)", rid))
    con:query(string.format(
       "UPDATE rental SET last_update = NOW() WHERE rental_id = %s", rid))
 end
 
 local TX = {
    tx_film_availability,
    tx_customer_touch,
    tx_rental_touch,
 }
 
 function event()
    con:query("BEGIN")
    local idx = tx_bag[math.random(#tx_bag)]
    TX[idx]()
    con:query("COMMIT")
 end