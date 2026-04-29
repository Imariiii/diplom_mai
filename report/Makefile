# Makefile для сборки дипломной работы
# Компилятор: XeLaTeX + latexmk

PROJECT = main
TEX = $(PROJECT).tex
PDF = $(PROJECT).pdf

# Флаги для latexmk
LATEXMK = latexmk
LATEXMK_FLAGS = -xelatex -pdf -interaction=nonstopmode -shell-escape -synctex=1

.PHONY: all clean cleanall view

all: $(PDF)

$(PDF): $(TEX)
	latexmk -xelatex -pdf -interaction=nonstopmode -shell-escape -f main.tex

# Просмотр PDF (Linux: evince, можно заменить на ваш просмотрщик)
view: $(PDF)
	evince $(PDF) &

# Очистка временных файлов (без удаления PDF)
clean:
	$(LATEXMK) -c
	rm -f *.xdv *.bbl *.run.xml *.synctex.gz

# Полная очистка (включая PDF, лог, вспомогательные файлы)
cleanall:
	$(LATEXMK) -C
	rm -f *.xdv *.run.xml

# Пересборка с нуля (полная очистка + сборка)
rebuild: cleanall all

# Для справки
help:
	@echo "Доступные цели:"
	@echo "  all      - собрать PDF (по умолчанию)"
	@echo "  view     - открыть PDF в просмотрщике (evince)"
	@echo "  clean    - удалить временные файлы, оставив PDF"
	@echo "  cleanall - удалить все сгенерированные файлы, включая PDF"
	@echo "  rebuild  - cleanall + all"