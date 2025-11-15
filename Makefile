SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c


streamlit-dev:
	poetry run streamlit run streamlit_app.py

diagnose:
	#poetry install && cd eval && poetry run python3 diagnose.py 2> /dev/null
	poetry install && cd eval && poetry run python3 diagnose.py

score:
	poetry install && cd eval && poetry run python3 score.py

clean_eval:
	rm -rf eval/results/*