# CSV fixtures (Format A)

Synthetic. Authored for this eval corpus. Not derived from any real merchant's
catalog or private data. (AGENTS.md §7 requires a provenance note per fixture;
a CSV has no envelope to carry one, so it is recorded here, per file.)

Column vocabulary is PRD §5.1's documented Shopify product CSV export set.

| File | Provenance | Intent |
| --- | --- | --- |
| `csv-simple.csv` | Synthetic | One product, one variant, no options. The floor case. |
| `csv-variants.csv` | Synthetic | One product across several rows: two options, three variants, a media-only row, product-level cells populated only on the first row, and two metafield columns (one an exact taxonomy key, one not). |
| `csv-multi-product.csv` | Synthetic | Three products in one file, including Unicode values, a quoted cell containing commas, and a quoted description containing a newline. |
| `csv-empty-product.csv` | Synthetic | A product with a title and handle and nothing else — no variant row at all. |
| `csv-unknown-columns.csv` | Synthetic | Documented columns the NPR has no member for, plus columns nobody has defined. Both must survive in `raw_extras`. |
| `csv-malformed.csv` | Synthetic | One ragged row, one row with no `URL handle`, one handle group with no `Title`, and a duplicated SKU inside a product. Each must be named in a run error, and the sound rows must still normalize. |
| `csv-inheritance-trap.csv` | Synthetic | A colour stated on one variant only. Nothing may copy it onto the other two. |
