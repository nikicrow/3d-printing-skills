# SVG input and color mapping

The generator supports ordinary SVG paths and the basic shapes converted by
`svgpathtools`. It reads solid fills and strokes, inline styles, inherited XML
presentation attributes, simple CSS class/ID rules, element IDs, and Inkscape
labels. Curves are flattened at print resolution before meshing.

Raster images, gradients, patterns, masks, clipping paths, filters, text that
has not been converted to paths, and opacity effects cannot become distinct
print materials reliably. When encountered, ask for a plain SVG with text
converted to paths and appearance expanded to solid fills/strokes. Transparent
or `none` paint is ignored.

Selectors supplied with `--color-map` work as follows:

- `id:leaves=#34A853` matches only element ID `leaves`.
- `label:Carrot top=#34A853` matches an Inkscape label.
- `fill:#00ff00=#34A853` matches a normalized source fill or stroke color.
- `leaves=#34A853` tries ID, label, then source color.

Later SVG elements paint over earlier elements. The final visible pixels are
made disjoint before extrusion, preventing coincident colored solids. Regions
sharing an output color share one material assignment even if their geometry
is disconnected.

The default base follows the filled artwork silhouette and closes interior
gaps before adding the border. If the dilated artwork still has disconnected
islands, the generator stops: a loose island would not be a usable keychain.
Increase `--border-width` or edit the SVG so the pieces touch.
