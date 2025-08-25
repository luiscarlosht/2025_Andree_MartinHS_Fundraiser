# -------- Makefile for 2025_Andree_MartinHS_Fundraiser --------
# Usage examples:
#   make wa-dry LIMIT=10
#   make sms-dry START=100 LIMIT=50
#   make wa-send START=0 LIMIT=200
#   make sms-send START=0 LIMIT=200
#   make report
#   make serve       # run the Flask webhook locally (port 5000)
# --------------------------------------------------------------

PYTHON ?= python

# CSV inputs produced by your prep scripts
WA_CSV  ?= whatsapp_contacts.csv
SMS_CSV ?= sms_contacts.csv

# Batching knobs (override per-invocation)
START ?= 0
LIMIT ?=

# Delay between sends (override if needed)
DELAY ?=

# Helper: source .env (if present) for each recipe
define LOAD_ENV
if [ -f .env ]; then set -a; . ./.env; set +a; fi
endef

# ---------- DRY RUNS (no messages sent) ----------
.PHONY: wa-dry sms-dry
wa-dry:
	@$(LOAD_ENV); \
	$(PYTHON) send_messages.py "$(WA_CSV)" WA_TEMPLATE --dry-run --start-from $(START) $(if $(LIMIT),--limit $(LIMIT),) $(if $(DELAY),--delay $(DELAY),)

sms-dry:
	@$(LOAD_ENV); \
	$(PYTHON) send_messages.py "$(SMS_CSV)" SMS --dry-run --start-from $(START) $(if $(LIMIT),--limit $(LIMIT),) $(if $(DELAY),--delay $(DELAY),)

# ---------- REAL SENDS ----------
.PHONY: wa-send sms-send
wa-send:
	@$(LOAD_ENV); \
	$(PYTHON) send_messages.py "$(WA_CSV)" WA_TEMPLATE --start-from $(START) $(if $(LIMIT),--limit $(LIMIT),) $(if $(DELAY),--delay $(DELAY),)

sms-send:
	@$(LOAD_ENV); \
	$(PYTHON) send_messages.py "$(SMS_CSV)" SMS --start-from $(START) $(if $(LIMIT),--limit $(LIMIT),) $(if $(DELAY),--delay $(DELAY),)

# ---------- REPORT ----------
# Reads sent_log.csv + status_log.csv and prints a summary.
# Also writes retry_list.csv, pending_list.csv, no_callback_list.csv
.PHONY: report
report:
	@$(LOAD_ENV); \
	$(PYTHON) report_delivery.py

# ---------- FLASK WEBHOOK (local) ----------
.PHONY: serve
serve:
	@$(LOAD_ENV); \
	export FLASK_ENV=development; \
	$(PYTHON) 2025_Andree_Fundraiser_MartinHS_Band.py
