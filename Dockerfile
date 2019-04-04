FROM python:stretch
RUN pip install \
	requests \
	cached_property \
	pystache \
	pyyaml \
	flask \
	bs4
WORKDIR /fiend_sucker
#COPY database.py decks genanki styles sucker.py templates /fiend_sucker
COPY . /fiend_sucker/
CMD python3 sucker.py

