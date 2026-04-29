# maps · cassette.help · MIT
# nota — dev setup and maintenance

BIN       := $(HOME)/.bin/nota
SRC       := $(HOME)/dev/nota/bin/nota

.PHONY: dev check clean

## dev: create ~/.bin/nota symlink (run once on new machine)
dev:
	@mkdir -p $(HOME)/.bin
	@if [ -L $(BIN) ] && [ "$$(readlink $(BIN))" = "$(SRC)" ]; then \
	  echo "symlink already correct: $(BIN) -> $(SRC)"; \
	else \
	  ln -sf $(SRC) $(BIN) && echo "linked: $(BIN) -> $(SRC)"; \
	fi
	@chmod +x $(SRC)

## check: syntax-check all Python source files
check:
	@echo "checking syntax..."
	@find src bin -name '*.py' -o -name 'nota' | xargs python3 -m py_compile && echo "ok"

## clean: remove compiled bytecode
clean:
	@find . -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null; \
	 find . -name '*.pyc' -delete 2>/dev/null; \
	 echo "cleaned"
