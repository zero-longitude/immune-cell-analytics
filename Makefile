.PHONY: setup pipeline dashboard clean

# Install all dependencies.
setup:
	pip install -r requirements.txt

pipeline:
	python load_data.py
	python analysis.py

# Start the local server for the app
dashboard:
	streamlit run app.py

# Optional cleaning
clean:
	rm -f cell_counts.db
	rm -rf outputs