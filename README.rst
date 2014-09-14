Hammersmith Ukulele Group arrangements
======================================

Can be rendered to pdf using our beefed-up version of chordlab__::

    # set up a virtualenv, e.g.
    virtualenv env
    ./env/bin/pip install -r requirements.txt

    # Fetch the external fonts
    git submodule init
    git submodule update

    # then you can activate the virtualenv and use make to create the pdfs
    source env/bin/activate
    make

.. __: https://github.com/hammeruke/chordlab
