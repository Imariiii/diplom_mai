-- Sakila mixed_light validation — зеркало активного bundle mixed_light::Sakila::common
-- workload_mode=query: один SQL на event(), без BEGIN/COMMIT
-- Веса: 30 select PK, 20 update, 20 join, 15 insert, 15 select FK

if sysbench.cmdline.command == nil then
   error("Укажите команду: run")
end

if sysbench.cmdline.command ~= "run" then
   if sysbench.cmdline.command == "help" then
      print("Использование: sysbench sakila_mixed_light_validation.lua --threads=N --events=M run")
      print("Прогрев: отдельный прогон --time=10 run")
      print("Метрика sysbench events/s сопоставляйте с throughput (QPS) в query mode")
   end
   return
end

sysbench.cmdline.options = {
   id_sample_limit = {"Сколько значений сэмплировать (как backend LIMIT 1000)", 1000},
}

local function rand_order_clause(drv_name)
   if drv_name == "pgsql" then
      return "ORDER BY random()"
   end
   return "ORDER BY RAND()"
end

local function sql_escape(value)
   return tostring(value):gsub("'", "''")
end

local function load_value_pool(con, drv_name, table_name, column_name, limit)
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
      error(string.format("Пустой пул: %s.%s", table_name, column_name))
   end
   return pool
end

local function pick(pool)
   return pool[math.random(#pool)]
end

local rental_ids
local rental_last_updates
local customer_ids
local staff_ids
local payment_amounts
local payment_dates
local query_bag

function thread_init()
   drv = sysbench.sql.driver()
   con = drv:connect()
   math.randomseed(os.time() + sysbench.tid)

   local lim = sysbench.opt.id_sample_limit
   rental_ids = load_value_pool(con, drv:name(), "rental", "rental_id", lim)
   rental_last_updates = load_value_pool(con, drv:name(), "rental", "last_update", lim)
   customer_ids = load_value_pool(con, drv:name(), "customer", "customer_id", lim)
   staff_ids = load_value_pool(con, drv:name(), "staff", "staff_id", lim)
   payment_amounts = load_value_pool(con, drv:name(), "payment", "amount", lim)
   payment_dates = load_value_pool(con, drv:name(), "payment", "payment_date", lim)

   query_bag = {}
   for _ = 1, 30 do table.insert(query_bag, 1) end
   for _ = 1, 20 do table.insert(query_bag, 2) end
   for _ = 1, 20 do table.insert(query_bag, 3) end
   for _ = 1, 15 do table.insert(query_bag, 4) end
   for _ = 1, 15 do table.insert(query_bag, 5) end
end

function thread_done()
   con:disconnect()
end

local function q_select_rental_pk()
   local rid = pick(rental_ids)
   con:query(string.format("SELECT * FROM rental WHERE rental_id = %s", rid))
end

local function q_update_rental()
   local rid = pick(rental_ids)
   local lu = sql_escape(pick(rental_last_updates))
   con:query(string.format(
      "UPDATE rental SET last_update = '%s' WHERE rental_id = %s", lu, rid))
end

local function q_join_rental_customer()
   local rid = pick(rental_ids)
   con:query(string.format(
      "SELECT a.*, b.* FROM rental a JOIN customer b ON a.customer_id = b.customer_id WHERE a.rental_id = %s",
      rid))
end

local function q_insert_payment()
   local cid = pick(customer_ids)
   local sid = pick(staff_ids)
   local rid = pick(rental_ids)
   local amt = pick(payment_amounts)
   local pdate = sql_escape(pick(payment_dates))
   con:query(string.format(
      "INSERT INTO payment (customer_id, staff_id, rental_id, amount, payment_date) VALUES (%s, %s, %s, %s, '%s')",
      cid, sid, rid, amt, pdate))
end

local function q_select_rental_by_customer()
   local cid = pick(customer_ids)
   con:query(string.format(
      "SELECT * FROM rental WHERE customer_id = %s LIMIT 100", cid))
end

local QUERY_FUNCS = {
   q_select_rental_pk,
   q_update_rental,
   q_join_rental_customer,
   q_insert_payment,
   q_select_rental_by_customer,
}

function event()
   local idx = query_bag[math.random(#query_bag)]
   QUERY_FUNCS[idx]()
end
