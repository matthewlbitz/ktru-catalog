# KTRU record library

A small, read-only browser for the station catalog. Courier New, dark brown, cream, and goldenrod. Requires Python 3.9 or later. No packages or build step.

## On the station computer

Open a terminal in the `KTRU` folder and run:

```sh
git clone https://github.com/matthewlbitz/ktru-catalog.git
cd ktru-catalog
python3 server.py
```

On Windows use `py server.py`. Open **http://localhost:3004** and keep the terminal open. `start.command` (macOS) and `start.bat` (Windows) are also included.

The folder layout is:

```
KTRU/
  data/masterAlbums.db
  ktru-catalog/
    server.py
    public/
  [other applications]
```

For a different database location or occupied port:

```sh
python3 server.py --db /path/to/masterAlbums.db --port 3005
```

To update later, run `git pull` inside `ktru-catalog` and restart the app.

## Search

Combine artist, album, primary genre, secondary genre, inclusive year range, and exact shelf filters. For a single year, enter it in both year boxes. The main search also matches barcodes, style, labels, Discogs IDs, and calculated shelf IDs. Click an album for its cover, metadata, identifiers, and tracklist. Search addresses can be bookmarked. Escape closes the popup; `/` focuses search.

## Catalog rules

- Reads `rainbow_albums` from `../data/masterAlbums.db`. Only records with a nonblank assigned `barcode` are included, in search, detail responses, counts, and shelf numbering.
- SQLite is opened in read-only mode with `query_only` enabled. No schema, indexes, rows, or workflow history are written. Database changes are picked up on subsequent requests.
- Shelf precedence: `final_shelf`, `new_shelf`, `new_shelf_label`, then `shelf_label`.
- `14D.37` means position 37 among all eligible records on shelf 14D. Order is normalized `artist_sort` (falling back to artist), then album title, year, barcode, and database ID. Numeric segments sort naturally. Search filters and display sort do not change shelf IDs. Shelf positions are calculated catalog order, not confirmed physical inventory, and can shift as albums or assignments change.
- Existing format fields take precedence. Otherwise `V.` shelves count as vinyl and other records count as CD, matching the existing master CD catalog. The current supplied database has no explicit format column and contains barcoded CD records; the Vinyl filter can therefore legitimately return no results. No unbarcoded vinyl records are imported from other catalogs.
- Missing metadata appears as a dash. Artwork comes from existing Discogs URLs and needs internet access; failed images use a simple placeholder. Metadata and searching work offline. No external fonts, analytics, or account system.
- The server listens only on this computer. GitHub holds the application source, not the station database. This is a local Python app, not a GitHub Pages site.

## Checks

```sh
python3 -m unittest discover -s tests
```
