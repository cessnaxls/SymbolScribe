# Whole-glyph candidate detector (v2)

This patch replaces the previous staff-subtraction component proposal stage.

- Detects five-line staves and measures local line spacing.
- Removes long horizontal rules before joining local glyph fragments.
- Filters thin staff-line debris, tiny dots and oversized connected artwork.
- Restricts joins to glyph-scale neighborhoods, rather than joining nearby music indiscriminately.
- Detects barlines separately from the original image when they cross an entire staff.
- Deduplicates overlapping candidate boxes and retains manual boxing.
- Keeps the existing ordered labeling UI, on-device saved examples, MXL and PDF export, and Render Free blueprint.

**Caution:** This is a conservative candidate proposer, not a complete OMR recognizer. Some historical staves and glyphs are still missed. In particular, the user-provided screenshot was recognized as two staves; this is incomplete. All music still needs manual review and correction. Do not infer proof of transcription accuracy from a reduced box count.
