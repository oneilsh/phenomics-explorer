SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c


streamlit-dev:
	poetry run streamlit run streamlit_app.py

eval:
	poetry run python3 eval.py > eval_result.txt