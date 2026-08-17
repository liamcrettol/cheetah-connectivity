# Local builds. Same commands the CI runs, so a green build here means a green
# build there.

.PHONY: all paper protocol single clean watch

all: paper protocol

paper:
	cd tex && latexmk -pdf main.tex

protocol:
	cd protocol && latexmk -pdf protocol.tex

# Regenerate the paste-anywhere single-file version from the split sources.
# The split version stays canonical; this is a derived artifact.
single:
	python3 tools/flatten.py

# Continuous rebuild while writing.
watch:
	cd tex && latexmk -pdf -pvc main.tex

clean:
	cd tex && latexmk -C
	cd protocol && latexmk -C
