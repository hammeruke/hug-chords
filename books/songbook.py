"""
rst2pdf extension to build a songbook.

The songbook is a mix of a normal reST document (to render as PDF) and a set of
songbooks rendered by other means and available as pdf.

Currently there is a base ``include-pdf`` directive implemented. What is
planned is a tighter interaction with chordlab, e.g. to fix the page numbers in
the songsheets and read the songs titles, this kind of stuff. That's TODO.

The usage is something like::

    rst2pdf -e songbook -o sample.pdf sample.rst

See `sample.rst` for an input file example.

"""

#
# Additional reST directives that we can add to the document
#

from docutils.parsers import rst
from docutils.nodes import Element
from docutils.parsers.rst import directives

class IncludePdf(rst.Directive):
    """A custom directive that allows to include an entire pdf in the document
    """
    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = True
    option_spec = {}
    has_content = False

    def run(self):
        node = IncludedPdfElement(filename=self.arguments[0])
        return [node]

directives.register_directive("include-pdf", IncludePdf)


#
# This is the bit that merges rst2pdf with reportlab. Here we only build the
# new flowable when we find the docutils node representing it. The real action
# will be performed later, when the flowable's apply() is called.
#

from collections import namedtuple

from rst2pdf.basenodehandler import NodeHandler
from reportlab.platypus import ActionFlowable


class IncludedPdfElement(Element):
    children = ()

    #def gen_flowable(self, style_options):
    def gen_flowable(self):
        f = IncludedPdfFlowable()
        f.attributes = self.attributes
        return f

class HandleIncludedPdf(NodeHandler, IncludedPdfElement):
    def gather_elements(self, client, node, style):
        # style_options = {
        #     'font': client.styles['aafigure'].fontName,
        #     }
        # return [node.gen_flowable(style_options)]
        return [node.gen_flowable()]


#
# The flowable lives in reportlab. Maintain the page count after the inclusion
# of a new pdf and record the inclusion position.
# TODO: Probably must add a toc element of some sort
#

from pyPdf import PdfFileReader, PdfFileWriter

Joint = namedtuple("Joint", "after_page added_pages npages file")
joints = []
added_pages = 0

class IncludedPdfFlowable(ActionFlowable):
    def apply(self, frame):
        global added_pages

        # Read the number of pages of the doc to merge
        fn = self.attributes['filename']
        f = open(fn)
        pdf = PdfFileReader(f)
        npages = pdf.getNumPages()
        f.close()

        # Where to record this document
        after_page = frame.page - (frame.frame._atTop and 1 or 0)
        joints.append(Joint(after_page, added_pages, npages, fn))
        added_pages += npages

        # finish the page if it was already started
        if not frame.frame._atTop:
            frame.handle_pageBreak()
        # skip as many pages
        for i in xrange(npages):
            frame.handle_pageBegin()


#
# Monkeypatching of rst2pdf
# After the creation of the original document merge it with the other pieces.
#

from rst2pdf import createpdf

class JoiningRstToPdf(createpdf.RstToPdf):
    def createPdf(self, output, **kwargs):
        super(JoiningRstToPdf, self).createPdf(output=output, **kwargs)

        openfiles = []  # the pdf libraries wants the files open when writing

        # Open the file just generated
        f = open(output)
        openfiles.append(f)
        doc = PdfFileReader(f)

        pdf = PdfFileWriter()
        used_page = 0       # pages used in the original doc
        for joint in joints:
            # Add the document pages before this joint
            for i in range(used_page, joint.after_page - joint.added_pages):
                pdf.addPage(doc.getPage(i))
                used_page += 1

            # add the merged document
            f1 = open(joint.file)
            openfiles.append(f1)
            doc1 = PdfFileReader(f1)
            for i in xrange(doc1.getNumPages()):
                pdf.addPage(doc1.getPage(i))

        # Add the last pages of the doc
        for i in range(used_page, doc.getNumPages()):
            pdf.addPage(doc.getPage(i))

        # Write the joined file
        f = open(output, 'wb')
        pdf.write(f)
        f.close()

        # Now close everything you got open
        for f in openfiles:
            f.close()

def install(createpdf, options):
    createpdf.RstToPdf = JoiningRstToPdf
