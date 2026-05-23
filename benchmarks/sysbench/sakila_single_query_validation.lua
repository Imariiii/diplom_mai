-- Один SQL на event (query mode) — для сравнения с custom_sql в системе
-- По умолчанию: SELECT * FROM rental WHERE rental_id = 1
-- Переопределение: --lua-var=query_sql="'SELECT ...'"

if sysbench.cmdline.command == nil then
   error("Укажите команду: run")
end

if sysbench.cmdline.command ~= "run" then
   if sysbench.cmdline.command == "help" then
      print("Один запрос на event. Сопоставляйте events/s с throughput (QPS).")
      print("Пример: sysbench sakila_single_query_validation.lua --threads=30 --events=3000 run ...")
   end
   return
end

sysbench.cmdline.options = {
   query_sql = {"SQL для каждого event", "SELECT * FROM rental WHERE rental_id = 1"},
}

function thread_init()
   drv = sysbench.sql.driver()
   con = drv:connect()
end

function thread_done()
   con:disconnect()
end

function event()
   con:query(sysbench.opt.query_sql)
end
