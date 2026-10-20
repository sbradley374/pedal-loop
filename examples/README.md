# Example export

`brown-29.8mi.gpx` is an actual output from the bundled OSM snapshot and default preferences (30 miles, traffic 0.8, stops 0.6, hills neutral, unknown pavement allowed).

- 29.8 miles; 1,983 track points; closed loop.
- 0.2% repeated distance; 43.1% of distance without a surface tag.
- Start snapped 36 m from the requested Brown University point.
- Terrain elevations now included at all 1,983 track points. The smoothed UI estimates ~1,024 ft ascent and ~1,020 ft descent; external GPX apps may calculate different totals.

This is a candidate for inspecting the software output, **not an audited cycling recommendation**. Turn restrictions and current conditions are not modeled. Verify all access, surface, and road conditions before riding. OSM attribution is embedded in the file.

## Burlington integration examples

The `burlington-*.gpx` files demonstrate the same routing engine on a second region. A 5-mile target returned 5.1 miles / ~318 ft ascent. At a 10-mile target, flatter preference returned 10.0 miles / ~518 ft, and hill preference returned 10.8 miles / ~598 ft. These are heuristic outputs, not matched-distance experiments or audited ride recommendations. Terrain source attribution is embedded in each file.
