PDFDIR?=pdfs
CHORDS=$(wildcard chords/*.cho) $(wildcard chords/*/*.cho)
PDFS=$(patsubst chords/%.cho,$(PDFDIR)/%.pdf,$(CHORDS))
DIRS=$(shell find chords -type d)
SONGBOOKS=$(patsubst chords/%,$(PDFDIR)/%-songbook.pdf,$(DIRS))
CHORDLAB=chordlab
STYLE=style/hammersmith.ini

.PHONY: clean

all: $(PDFS) $(SONGBOOKS)

$(PDFDIR)/%.pdf: chords/%.cho $(STYLE)
	mkdir -p `dirname $@`
	$(CHORDLAB) -p 842x595 --style $(STYLE) --ukulele -o $@ $<

$(PDFDIR)/%-songbook.pdf: chords/%/*.cho $(STYLE)
	mkdir -p `dirname $@`
	$(CHORDLAB) -p 842x595 --style $(STYLE) --ukulele -o $@ chords/$*/*.cho

$(PDFDIR)/%-screen.pdf: chords/%.cho $(STYLE)
	mkdir -p `dirname $@`
	$(CHORDLAB) -p 1000x560 --style $(STYLE) --ukulele -o $@ $<

clean:
	rm -rf $(PDFDIR)
