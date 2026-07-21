# **************************************************************************** #
#                                  COLORS                                      #
# **************************************************************************** #

RESET   := \033[0m
BOLD    := \033[1m

RED     := \033[31m
GREEN   := \033[32m
YELLOW  := \033[33m
BLUE    := \033[34m
MAGENTA := \033[35m
CYAN    := \033[36m
WHITE   := \033[37m

SUCCESS = @printf "$(GREEN)✔$(RESET) %s\n"
INFO    = @printf "$(CYAN)➜$(RESET) %s\n"
WARN    = @printf "$(YELLOW)⚠$(RESET) %s\n"
TITLE   = @printf "$(BOLD)$(MAGENTA)\n========== %s ==========\n$(RESET)"
# **************************************************************************** #
#                                   ASCII                                      #
# **************************************************************************** #

spinner = \
( \
while true; do \
	for c in '⠋' '⠙' '⠹' '⠸' '⠼' '⠴' '⠦' '⠧' '⠇' '⠏'; do \
		printf "\r\033[K$(CYAN)%s %s$(RESET)" "$(1)" "$$c"; \
		sleep 0.1; \
	done; \
done \
) & \
PID=$$!; \
$(2); \
kill $$PID 2>/dev/null; \
wait $$PID 2>/dev/null; \
printf "\r\033[K$(GREEN)✓ $(1) complete.$(RESET)\n"

BANNER = \
printf "$(CYAN)"; \
printf "██████╗ ██████╗ ██╗███╗   ███╗██╗███████╗███╗   ██╗ ██████╗ ██╗███╗   ██╗███████╗\n"; \
printf "██╔══██╗██╔══██╗██║████╗ ████║██║██╔════╝████╗  ██║██╔════╝ ██║████╗  ██║██╔════╝\n"; \
printf "██████╔╝██████╔╝██║██╔████╔██║██║█████╗  ██╔██╗ ██║██║  ███╗██║██╔██╗ ██║█████╗  \n"; \
printf "██╔═══╝ ██╔══██╗██║██║╚██╔╝██║██║██╔══╝  ██║╚██╗██║██║   ██║██║██║╚██╗██║██╔══╝  \n"; \
printf "██║     ██║  ██║██║██║ ╚═╝ ██║██║███████╗██║ ╚████║╚██████╔╝██║██║ ╚████║███████╗\n"; \
printf "╚═╝     ╚═╝  ╚═╝╚═╝╚═╝     ╚═╝╚═╝╚══════╝╚═╝  ╚═══╝ ╚═════╝ ╚═╝╚═╝  ╚═══╝╚══════╝\n"; \
printf "$(RESET)\n";

# **************************************************************************** #
#                                 Variables                                    #
# **************************************************************************** #
VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
MAIN := main.py
PACKAGE := primiengine

# **************************************************************************** #
#                                  Actions                                     #
# **************************************************************************** #

all: install

install: banner
	@printf "$(CYAN)"
	@printf "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
	@printf "        Preparing the environement\n"
	@printf "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
	@printf "$(RESET)"
	@test -d $(VENV) || python3 -m venv $(VENV)
	@$(PIP) install --upgrade pip >/dev/null
	@$(call spinner,Installing dependencies,$(PIP) install -e . >/dev/null)
	@$(PIP) install flake8 mypy build >/dev/null
	
	@printf "\n$(GREEN)🗝  The Engine is ready. Have Fun!$(RESET)\n"

banner:
	@$(BANNER)
	@printf "$(CYAN)═══════════════════════════════════════════════$(RESET)\n"
	@printf "$(GREEN)   Welcome to PRIMIENGINE!$(RESET)\n"
	@printf "$(YELLOW)   Every road lead somewhere... let's ride.$(RESET)\n"
	@printf "$(CYAN)═══════════════════════════════════════════════$(RESET)\n\n"


build:
	$(TITLE) "Building $(PACKAGE) package"
	@$(call spinner,Building $(PACKAGE) package,$(PYTHON) -m build >/dev/null 2>&1)
	@find dist -name "*.whl" -exec cp {} . \;
	@find dist -name "*.tar.gz" -exec cp {} . \;

package-install:
	$(TITLE) "Installing built package"
	@$(call spinner,Installing built package $(PACKAGE) package,$(PIP) install *.whl --force-reinstall >/dev/null 2>&1)

run:
	@printf "$(BLUE)"
	@printf "╔══════════════════════════════════════╗\n"
	@printf "║        Testing the engine...         ║\n"
	@printf "╚══════════════════════════════════════╝\n"
	@printf "$(RESET)"
	@$(PYTHON) $(MAIN)

lint:
	$(TITLE) "Running lint checks"
	-flake8 . --exclude .venv,minilibx-linux
	mypy --warn-return-any --warn-unused-ignores --ignore-missing-imports \
		--disallow-untyped-defs --check-untyped-defs .
	$(SUCCESS) "Lint complete!"

clean:
	$(TITLE) "Cleaning project"
	rm -rf */__pycache__
	rm -rf .mypy_cache
	rm -rf dist
	rm -rf logs
	rm -rf build
	rm -rf *.egg-info
	@if [ -d "$(MLX_DIR)" ]; then \
		$(MAKE) -C $(MLX_DIR) clean; \
	fi
	rm -f maze.txt
	$(SUCCESS) "Clean complete!"

fclean: clean
	$(TITLE) "Full clean"
	rm -f *.whl
	rm -f *.tar.gz
	rm -rf .venv
	$(SUCCESS) "Everything removed!"

re: fclean install

.PHONY: all install build run lint clean fclean