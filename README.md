# Jupyter Book Slideshow POC

## Maintenance

**This is just a proof of concept, for a version of `jupyter-book` that is already outdated. Furthermore, it is terribly hacky. I have neither the time to maintain this, nor sufficient knowledge of the inner workings of `jupyter-book`, `MyST-NB`, `sphinx` etc. to implement it properly.**

## Building

```
$ python -m venv .venv
$ source .venv/bin/activate
$ pip install -r requirements.txt
$ jb build .
```

## How it works

The code to make this work is in `local_extensions/slides`. It is loaded as a local sphinx extension at the bottom of `_config.yml`.

1. We overwrite the MyST-NB Parser to insert a directive like this to the beginning of each cell, containing the cell's metadata:
   ````
   ```{cell-meta}
   {"slideshow": {"slide_type": "slide"}}
   ```
   ````
   (see `parser.py`)

2. This directive emits a custom node in the docutils tree, that renders into an invisible json script tag like this:
   ```html
   <script type="application/json" data-cell-meta="">
       {"slideshow": {"slide_type": "slide"}}
   </script>
   ```
   (see `directive.py`)

3. If there is such a custom node in the tree (and it has `slideshow` metadata), we include all the required js/css files for `reveal.js`, our custom js file, and add the slideshow button
   
   (see `\_\_init\_\_.py`)

4. When the slideshow button is pressed, we search for the `<script>` tags, take all the dom elements between them, and arrange them in the structure that `reveal.js` expects
   
   (see `static/present.js`)