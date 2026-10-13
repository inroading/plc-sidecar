# Observed ISPSoft `.isp` format

Evidence is from one EC3 ISPSoft 3.24 user project and six ISPSoft 3.24 example projects. These notes are observations for that set, not a guarantee for every `.isp` version or PLC family.

- Little-endian 32-bit value at header offset `0x98`: compressed block start. Observed values ranged from 164 to 2848, so the header length is **not** fixed.
- `0x94`: block size, including a six-byte prefix. At block start: `08 00`, then CRC32 of uncompressed payload (little-endian), then raw DEFLATE data.
- `0x58`: compressed block end in the user project; zero in all six examples. Update only when the original value equals the original block end. Reject an unexpected nonzero value.
- `0x7C`: uncompressed length in the user project; zero in all six examples. Update only when the original value equals the original payload length. Reject an unexpected nonzero value.
- Payload begins `<PROJECT>\r\n`; the projects observed used CRLF and contained `<TASK>`, `<POU>`, and `<NETWORK_START>` sections. Preserve the original newline and metadata encoding. The user project declared `Active_CodePage=936`.
- A user project had 40 trailing bytes after the block; the example projects had none. Preserve trailing bytes unchanged.
- Raw-DEFLATE compression level is inferred by searching for a level that reproduces the original file byte-for-byte. On observed files, levels 8 or 9 were among the matches. If no level matches, the generic pack command refuses the file.

LD node patterns observed in installed examples and the user project: `TYPE=1` normally-open contact, `2` normally-closed, `3` rising-edge, `13` OUT, `15` SET, `16` RST, `9` instruction, `10` comparator. The instruction node is bracketed by operand nodes (`11`, `12`) and end node (`7`). `NET_ID` is a per-POU network identifier. API values observed in ISPSoft's installed `DVP2AS_API.csv`: MOV 28, ADD 60, SUB 64, MUL 68, MODRD 270, MODWR 271. Validate against the target installation and a representative project before introducing other instructions or branch shapes.

If direct editing is necessary, keep a copy of the original, make targeted changes to decompressed bytes, and compare the output against the input at the POU/network level. Do not treat a valid CRC or self-consistent XML-like structure as a successful PLC compile.
