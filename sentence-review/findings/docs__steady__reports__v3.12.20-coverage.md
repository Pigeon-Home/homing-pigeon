# Findings — docs/steady/reports/v3.12.20-coverage.md

Source: docs/steady/reports/v3.12.20-coverage.md, reviewed at main cbb52068.
Sentence units: 373. Flagged: 16. Categories: pre-release 373, post-release 0.

The report is a sequence of same-day measurement passes; each pass has its file table and a what-this-pass-pins run. Short prose fragments between tables belong to the table or chart beside them.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "This report belongs to package 3.12.20." | pre-release | flows |  |
| 2 | "The previous measurement is v3.11.1. No new tag…" | pre-release | flows |  |
| 3 | "The chart below is where this report started,…" | pre-release | flows |  |
| 4 | "The status after it is the current tree." | pre-release | flows |  |
| 5 | "Measured on main at b529730 (`tests: file a…" | pre-release | flows |  |
| 6 | "4549 tests, OK, 22 skipped." | pre-release | flows |  |
| 7 | "367 seconds." | pre-release | flows |  |
| 8 | "; Covered ; Missed ; Total" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 9 | "Statements ; 96.8% ; 546 ; 16872" | pre-release | flows |  |
| 10 | "Branches ; 94.5% ; ;" | pre-release | flows |  |
| 11 | "Statements and branches ; 96.1% ; ;" | pre-release | flows |  |
| 12 | "The files still under 96%, by statements:" | pre-release | flows |  |
| 13 | "File ; Covered ; Missed" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 14 | "transport_extensions/dtls/__main__.py ; 74.2% ; 42" | pre-release | flows |  |
| 15 | "transport_extensions/email/__main__.py ; 74.4% ; 32" | pre-release | flows |  |
| 16 | "transport_extensions/nats/__main__.py ; 77.5% ; 47" | pre-release | flows |  |
| 17 | "resources.py ; 92.5% ; 14" | pre-release | flows |  |
| 18 | "oauth.py ; 92.9% ; 15" | pre-release | flows |  |
| 19 | "auditreport.py ; 93.5% ; 15" | pre-release | flows |  |
| 20 | "security.py ; 93.5% ; 15" | pre-release | flows |  |
| 21 | "mailbox.py ; 94.1% ; 11" | pre-release | flows |  |
| 22 | "dri.py ; 94.9% ; 20" | pre-release | flows |  |
| 23 | "detection.py ; 95.6% ; 8" | pre-release | flows |  |
| 24 | "runner.py, the largest file, is 96.6% (236 missed…" | pre-release | flows |  |
| 25 | "The three extension programs at 74–78% are the…" | pre-release | flows |  |
| 26 | "They open a socket or a broker, and…" | pre-release | flows |  |
| 27 | "What is left in the other files is…" | pre-release | flows |  |
| 28 | "Statement coverage, 40 cells, one cell is 2.5…" | pre-release | flows |  |
| 29 | "`runner/__init__.py` and `runner/_version.py` are one or two statements…" | pre-release | flows |  |
| 30 | "They are not on the chart. `channel.py` is…" | pre-release | flows |  |
| 31 | "The four `ext` rows are the transport extension…" | pre-release | flows |  |
| 32 | "Measured 2026-10-22 with coverage.py 7.16.2, on Python 3.11.2.…" | pre-release | flows |  |
| 33 | "4401 tests, OK, 22 skipped, 370 seconds under…" | pre-release | flows |  |
| 34 | "The skips are optional tools that were not…" | pre-release | flows |  |
| 35 | "Statements: 16872." | pre-release | flows |  |
| 36 | "Missed: 1107." | pre-release | flows |  |
| 37 | "Covered: 15765." | pre-release | flows |  |
| 38 | "Covered: 93.4%." | pre-release | flows |  |
| 39 | "Branches: 6840." | pre-release | flows |  |
| 40 | "Covered: 6163 (90.1%)." | pre-release | flows |  |
| 41 | "Missing: 677, of which 583 are only partly…" | pre-release | flows |  |
| 42 | "Statement and branch together, the number `coverage report`…" | pre-release | flows |  |
| 43 | "The 93.4% is statement coverage, the same kind…" | pre-release | flows |  |
| 44 | "That report's together figure was 93.1%." | pre-release | flows |  |
| 45 | "This run's together figure is 92.5%." | pre-release | flows |  |
| 46 | "The v3.11.1 report was 94.2% (15326 statements, 890…" | pre-release | flows |  |
| 47 | "Covered statements went from 14436 to 15765." | pre-release | flows |  |
| 48 | "The tree grew by 1546 statements." | pre-release | flows |  |
| 49 | "Misses rose by 217." | pre-release | flows |  |
| 50 | "The percent fell by 0.8 points." | pre-release | flows |  |
| 51 | "The new code is covered, and a few…" | pre-release | flows |  |
| 52 | "File ; 19 Oct ; Now ; Missed…" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 53 | "channel.py ; 68% ; 97% ; 3" | pre-release | flows |  |
| 54 | "dtlsproto.py ; 83% ; 88% ; 135" | pre-release | flows |  |
| 55 | "runner.py ; 97% ; 95% ; 340" | pre-release | flows |  |
| 56 | "install.py ; 99.9% ; 98.7% ; 23" | pre-release | flows |  |
| 57 | "transports.py ; 83% ; 84% ; 88" | pre-release | flows |  |
| 58 | "learning.py ; 82% ; 84% ; 62" | pre-release | flows |  |
| 59 | "detection.py ; 82% ; 82% ; 32" | pre-release | flows |  |
| 60 | "oauth.py ; 85% ; 85% ; 31" | pre-release | flows |  |
| 61 | "winlog.py ; 88% ; 88% ; 4" | pre-release | flows |  |
| 62 | "dri.py ; 91% ; 91% ; 34" | pre-release | flows |  |
| 63 | "`channel.py` was the bottom of the last chart…" | pre-release | flows |  |
| 64 | "Three statements remain." | pre-release | flows |  |
| 65 | "`dtlsproto.py` was the largest hole (177 missed)." | pre-release | flows |  |
| 66 | "It is 135 now." | pre-release | flows |  |
| 67 | "The handshake is still the body of what…" | pre-release | flows |  |
| 68 | "`runner.py` grew from 6343 statements and 175 missed…" | pre-release | flows |  |
| 69 | "The percent fell from 97.2 to 95.1. The…" | pre-release | flows |  |
| 70 | "`install.py` grew with host classification." | pre-release | flows |  |
| 71 | "Twenty-three statements missed." | pre-release | flows |  |
| 72 | "The ones that matter are the USB sysfs…" | pre-release | flows |  |
| 73 | "The scan is covered when the facts are…" | pre-release | flows |  |
| 74 | "The sysfs walk itself is not." | pre-release | flows |  |
| 75 | "`harness.py`, `posture.py`, `local_test.py`, and `setup.py` are still fully…" | pre-release | flows |  |
| 76 | "Both were 100% on 19 October." | pre-release | flows |  |
| 77 | "File ; Now ; Missed" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 78 | "protocol_v2.py ; 79% ; 75" | pre-release | flows |  |
| 79 | "personal_docs.py ; 86% ; 25" | pre-release | flows |  |
| 80 | "dtls extension ; 74% ; 42" | pre-release | flows |  |
| 81 | "email extension ; 74% ; 32" | pre-release | flows |  |
| 82 | "nats extension ; 78% ; 47" | pre-release | flows |  |
| 83 | "file extension ; 79% ; 30" | pre-release | flows |  |
| 84 | "`protocol_v2.py` was not on the last chart." | pre-release | flows |  |
| 85 | "Seventy-five statements missed, the lowest file that is…" | pre-release | flows |  |
| 86 | "The misses are the long job-id digest, the…" | pre-release | flows |  |
| 87 | "The happy path of a normal-length id is…" | pre-release | flows |  |
| 88 | "Two ids that differ only past the old…" | pre-release | flows |  |
| 89 | "`personal_docs.py` is the install-time warning." | pre-release | flows |  |
| 90 | "Twenty-five statements missed." | pre-release | flows |  |
| 91 | "They are the XDG `user-dirs.dirs` parser, a symlink,…" | pre-release | flows |  |
| 92 | "The ordinary home scan is covered." | pre-release | flows |  |
| 93 | "A relocated Documents folder, and a folder that…" | pre-release | flows |  |
| 94 | "The four extension programs are still the low…" | pre-release | flows |  |
| 95 | "They are processes the runner supervises." | pre-release | flows |  |
| 96 | "A unit test that stands up a live…" | pre-release | flows |  |
| 97 | "`jobcrypto.py` still misses seven statements." | pre-release | flows |  |
| 98 | "That is not the hole." | pre-release | flows |  |
| 99 | "From the repo root, with coverage.py installed." | pre-release | flows |  |
| 100 | "It is a measurement tool, not a project…" | pre-release | flows |  |
| 101 | "Install hypothesis first if you want the property…" | pre-release | flows |  |
| 102 | "Use Python 3.11 or newer. `tomllib` is not…" | pre-release | flows |  |
| 103 | "Expect about six minutes." | pre-release | flows |  |
| 104 | "Do not treat 93.4% as a target." | pre-release | flows |  |
| 105 | "The number moved because `runner.py` grew and `protocol_v2.py`…" | pre-release | flows |  |
| 106 | "The hole worth a test is the v2…" | pre-release | flows |  |
| 107 | "Not another point on the old core, and…" | pre-release | flows |  |
| 108 | "Measured again the same day, same command, after…" | pre-release | flows |  |
| 109 | "4425 tests, OK, 22 skipped, 363 seconds." | pre-release | flows |  |
| 110 | "Statements: 16872." | pre-release | flows |  |
| 111 | "Missed: 1038." | pre-release | flows |  |
| 112 | "Covered: 15834." | pre-release | flows |  |
| 113 | "Covered: 93.8%." | pre-release | flows |  |
| 114 | "Branches: 90.7%." | pre-release | flows |  |
| 115 | "Together: 92.9%." | pre-release | flows |  |
| 116 | "File ; Before ; After ; Missed after" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 117 | "protocol_v2.py ; 79% ; 95% ; 18" | pre-release | flows |  |
| 118 | "personal_docs.py ; 86% ; 96% ; 7" | pre-release | flows |  |
| 119 | "What the new tests actually pin: two job…" | pre-release | flows |  |
| 120 | "The warning now pins a phrase (`bank-statement`, `health_records`),…" | pre-release | flows |  |
| 121 | "What is left in those two files is…" | pre-release | flows |  |
| 122 | "Those are not the next hole." | pre-release | flows |  |
| 123 | "The extension programs are still 74% to 79%." | pre-release | flows |  |
| 124 | "Measured again the same day." | pre-release | flows |  |
| 125 | "4442 tests, OK, 22 skipped, 370 seconds." | pre-release | flows |  |
| 126 | "Statements: 16872." | pre-release | flows |  |
| 127 | "Missed: 962." | pre-release | flows |  |
| 128 | "Covered: 94.3%." | pre-release | flows |  |
| 129 | "Branches: 91.3%." | pre-release | flows |  |
| 130 | "Together: 93.4%." | pre-release | flows |  |
| 131 | "File ; Before this pass ; After ;…" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 132 | "winlog.py ; 88% ; 100% ; 0" | pre-release | flows |  |
| 133 | "detection.py ; 82% ; 94% ; 11" | pre-release | flows |  |
| 134 | "extensions.py ; 91% ; 96% ; 8" | pre-release | flows |  |
| 135 | "learning.py ; 84% ; 88% ; 48" | pre-release | flows |  |
| 136 | "oauth.py ; 85% ; 89% ; 24" | pre-release | flows |  |
| 137 | "dri.py ; 91% ; 92% ; 30" | pre-release | flows |  |
| 138 | "What this pass pins: a detection rule or…" | pre-release | flows |  |
| 139 | "The extension programs are still 74% to 79%." | pre-release | flows |  |
| 140 | "That is the floor until there is a…" | pre-release | flows |  |
| 141 | "Measured again the same day." | pre-release | flows |  |
| 142 | "4456 tests, OK, 22 skipped, 367 seconds." | pre-release | flows |  |
| 143 | "Statements: 16872." | pre-release | flows |  |
| 144 | "Missed: 897." | pre-release | flows |  |
| 145 | "Covered: 94.7%." | pre-release | flows |  |
| 146 | "Branches: 92.0%." | pre-release | flows |  |
| 147 | "Together: 93.9%." | pre-release | flows |  |
| 148 | "File ; Before this pass ; After ;…" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 149 | "learning.py ; 88% ; 96% ; 16" | pre-release | flows |  |
| 150 | "transports.py ; 84% ; 90% ; 56" | pre-release | flows |  |
| 151 | "oauth.py ; 89% ; 90% ; 21" | pre-release | flows |  |
| 152 | "dri.py ; 92% ; 93% ; 27" | pre-release | flows |  |
| 153 | "What this pass pins: the learning switches take…" | pre-release | flows |  |
| 154 | "Each feature kind (interpreter, tool, path, pathshape) has…" | pre-release | flows |  |
| 155 | "A torn ledger line and a record with…" | pre-release | flows |  |
| 156 | "A result id is taken from the job…" | pre-release | flows |  |
| 157 | "A file that changes between the two reads…" | pre-release | flows |  |
| 158 | "A result that does not land is not…" | pre-release | flows |  |
| 159 | "A DTLS secret file is read, and an…" | pre-release | flows |  |
| 160 | "`transports.py` is now 90%." | pre-release | flows |  |
| 161 | "What is left there is the child process…" | pre-release | flows |  |
| 162 | "The extension programs are still 74% to 79%." | pre-release | flows |  |
| 163 | "Measured again the same day." | pre-release | flows |  |
| 164 | "4468 tests, OK, 22 skipped, 363 seconds." | pre-release | flows |  |
| 165 | "Statements: 16872." | pre-release | flows |  |
| 166 | "Missed: 850." | pre-release | flows |  |
| 167 | "Covered: 95.0%." | pre-release | flows |  |
| 168 | "Branches: 92.2%." | pre-release | flows |  |
| 169 | "Together: 94.2%." | pre-release | flows |  |
| 170 | "File ; Before this pass ; After ;…" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 171 | "transports.py ; 90% ; 96% ; 24" | pre-release | flows |  |
| 172 | "learning.py ; 96% ; 97% ; 10" | pre-release | flows |  |
| 173 | "oauth.py ; 90% ; 93% ; 15" | pre-release | flows |  |
| 174 | "What this pass pins: a refresh that succeeds…" | pre-release | flows |  |
| 175 | "A reconciliation that cannot be written returns nothing,…" | pre-release | flows |  |
| 176 | "A candidate about a different tool is not…" | pre-release | flows |  |
| 177 | "A repeated feature is stored once." | pre-release | flows |  |
| 178 | "A broken extension folder is logged and the…" | pre-release | flows |  |
| 179 | "A frozen build rewrites `-m` into `--transport-extension-module`." | pre-release | flows |  |
| 180 | "A child that has been up for a…" | pre-release | flows |  |
| 181 | "An unreadable inbox does not hold startup." | pre-release | flows |  |
| 182 | "The log pump skips a blank line, reopens…" | pre-release | flows |  |
| 183 | "A process that will not die is killed,…" | pre-release | flows |  |
| 184 | "The same config reuses one supervisor." | pre-release | flows |  |
| 185 | "A symlink job and an oversize job are…" | pre-release | flows |  |
| 186 | "`dtlsproto.py` is still the handshake, at 88%." | pre-release | flows |  |
| 187 | "The extension programs are still 74% to 79%." | pre-release | flows |  |
| 188 | "Measured again the same day." | pre-release | flows |  |
| 189 | "4479 tests, OK, 22 skipped, 367 seconds." | pre-release | flows |  |
| 190 | "Statements: 16872." | pre-release | flows |  |
| 191 | "Missed: 811." | pre-release | flows |  |
| 192 | "Covered: 95.2%." | pre-release | flows |  |
| 193 | "Branches: 92.6%." | pre-release | flows |  |
| 194 | "Together: 94.5%." | pre-release | flows |  |
| 195 | "File ; Before this pass ; After ;…" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 196 | "dtlsproto.py ; 88% ; 90% ; 109" | pre-release | flows |  |
| 197 | "transports.py ; 96% ; 98% ; 11" | pre-release | flows |  |
| 198 | "learning.py ; 97% ; 99% ; 5" | pre-release | flows |  |
| 199 | "What this pass pins: an X25519 input that…" | pre-release | flows |  |
| 200 | "An extension block with a short header, an…" | pre-release | flows |  |
| 201 | "A key share and a PSK extension that…" | pre-release | flows |  |
| 202 | "An empty additional secret is not a name." | pre-release | flows |  |
| 203 | "A flight nobody answers for 60 seconds is…" | pre-release | flows |  |
| 204 | "An application message past the cap is refused,…" | pre-release | flows |  |
| 205 | "A KeyUpdate of the wrong shape is dropped;…" | pre-release | flows |  |
| 206 | "A channel file that cannot be read is…" | pre-release | flows |  |
| 207 | "A child that cannot be started is logged…" | pre-release | flows |  |
| 208 | "An inbox that already has a job does…" | pre-release | flows |  |
| 209 | "The log pump drops a poisoned line and…" | pre-release | flows |  |
| 210 | "A ledger trim that cannot replace the file…" | pre-release | flows |  |
| 211 | "What is left in `dtlsproto.py` is the rest…" | pre-release | flows |  |
| 212 | "The extension programs are still 74% to 79%." | pre-release | flows |  |
| 213 | "Measured again the same day." | pre-release | flows |  |
| 214 | "4489 tests, OK, 22 skipped, 370 seconds." | pre-release | flows |  |
| 215 | "Statements: 16872." | pre-release | flows |  |
| 216 | "Missed: 734." | pre-release | flows |  |
| 217 | "Covered: 95.6%." | pre-release | flows |  |
| 218 | "Branches: 93.4%." | pre-release | flows |  |
| 219 | "Together: 95.0%." | pre-release | flows |  |
| 220 | "File ; Before this pass ; After ;…" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 221 | "dtlsproto.py ; 90% ; 97% ; 33" | pre-release | flows |  |
| 222 | "What this pass pins, through the real client…" | pre-release | flows |  |
| 223 | "A HelloRetryRequest with no cookie." | pre-release | flows |  |
| 224 | "A Finished that does not verify, which kills…" | pre-release | flows |  |
| 225 | "A fatal alert in either direction." | pre-release | flows |  |
| 226 | "Application data before our Finished." | pre-release | flows |  |
| 227 | "A handshake fragment that is reassembled, and a…" | pre-release | flows |  |
| 228 | "A greeting that is not JSON." | pre-release | flows |  |
| 229 | "A ClientHello whose X25519 share is the zero…" | pre-release | flows |  |
| 230 | "A first flight that is an alert, a…" | pre-release | flows |  |
| 231 | "A replayed cookie-bearing hello, answered with the same…" | pre-release | flows |  |
| 232 | "A datagram that claims more bytes than it…" | pre-release | flows |  |
| 233 | "An empty inner plaintext." | pre-release | flows |  |
| 234 | "A dead session and an expired ticket, removed…" | pre-release | flows |  |
| 235 | "Thirty-three statements remain in `dtlsproto.py`." | pre-release | flows |  |
| 236 | "Two of them are the X25519 clamp, which…" | pre-release | flows |  |
| 237 | "The rest are a few server checks a…" | pre-release | flows |  |
| 238 | "The extension programs are still 74% to 79%." | pre-release | flows |  |
| 239 | "Measured again the same day." | pre-release | flows |  |
| 240 | "4492 tests, OK, 22 skipped, 368 seconds." | pre-release | flows |  |
| 241 | "Statements: 16872." | pre-release | flows |  |
| 242 | "Missed: 712." | pre-release | flows |  |
| 243 | "Covered: 95.8%." | pre-release | flows |  |
| 244 | "Branches: 93.6%." | pre-release | flows |  |
| 245 | "Together: 95.2%." | pre-release | flows |  |
| 246 | "File ; Before this pass ; After ;…" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 247 | "dtlsproto.py ; 97% ; 99% ; 9" | pre-release | flows |  |
| 248 | "The previous pass asserted "an alert came back"…" | pre-release | flows |  |
| 249 | "The key share in those hellos was two…" | pre-release | flows |  |
| 250 | "This pass builds a share the parser accepts,…" | pre-release | flows |  |
| 251 | "What it pins: no PSK modes is a…" | pre-release | flows |  |
| 252 | "No key share, a key share that does…" | pre-release | flows |  |
| 253 | "No pre-shared key is a missing extension." | pre-release | flows |  |
| 254 | "A PSK block that does not parse, or…" | pre-release | flows |  |
| 255 | "An identity the server does not have is…" | pre-release | flows |  |
| 256 | "An expired resumption ticket falls through to the…" | pre-release | flows |  |
| 257 | "Application data before the session is up is…" | pre-release | flows |  |
| 258 | "A client Finished that does not verify kills…" | pre-release | flows |  |
| 259 | "A cookie extension shorter than its length field…" | pre-release | flows |  |
| 260 | "A handshake header that claims 100 bytes and…" | pre-release | flows |  |
| 261 | "A second Finished on a live session is…" | pre-release | flows |  |
| 262 | "A KeyUpdate on the server is answered." | pre-release | flows |  |
| 263 | "Nine statements remain." | pre-release | flows |  |
| 264 | "Two are the X25519 clamp, which cannot run." | pre-release | flows |  |
| 265 | "The extension programs are still 74% to 79%." | pre-release | flows |  |
| 266 | "Measured again the same day." | pre-release | flows |  |
| 267 | "4498 tests, OK, 22 skipped, 364 seconds." | pre-release | flows |  |
| 268 | "Statements: 16872." | pre-release | flows |  |
| 269 | "Missed: 683." | pre-release | flows |  |
| 270 | "Covered: 96.0%." | pre-release | flows |  |
| 271 | "Branches: 93.7%." | pre-release | flows |  |
| 272 | "Together: 95.3%." | pre-release | flows |  |
| 273 | "File ; Before this pass ; After ;…" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 274 | "transport_extensions/file/__main__.py ; 79% ; 99% ; 2" | pre-release | flows |  |
| 275 | "The file pipe is a watched folder, so…" | pre-release | flows |  |
| 276 | "A file that is not UTF-8 is refused…" | pre-release | flows |  |
| 277 | "A file that disappears between the listing and…" | pre-release | flows |  |
| 278 | "A refusal whose note cannot be written still…" | pre-release | flows |  |
| 279 | "A refusal that cannot move the job leaves…" | pre-release | flows |  |
| 280 | "A result body with no trailing newline gets…" | pre-release | flows |  |
| 281 | "A seen-mark that cannot be written is not…" | pre-release | flows |  |
| 282 | "A pass that throws is logged, and the…" | pre-release | flows |  |
| 283 | "Two lines remain: the script entry, and the…" | pre-release | flows |  |
| 284 | "Measured again the same day." | pre-release | flows |  |
| 285 | "4512 tests, OK, 22 skipped, 365 seconds." | pre-release | flows |  |
| 286 | "Statements: 16872." | pre-release | flows |  |
| 287 | "Missed: 650." | pre-release | flows |  |
| 288 | "Covered: 96.1%." | pre-release | flows |  |
| 289 | "Branches: 94.0%." | pre-release | flows |  |
| 290 | "Together: 95.5%." | pre-release | flows |  |
| 291 | "File ; Before this pass ; After ;…" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 292 | "senses.py ; 95% ; 98% ; 6" | pre-release | flows |  |
| 293 | "extensions.py ; 96% ; 99% ; 3" | pre-release | flows |  |
| 294 | "detection.py ; 94% ; 96% ; 8" | pre-release | flows |  |
| 295 | "dri.py ; 93% ; 95% ; 20" | pre-release | flows |  |
| 296 | "protocol_v2.py ; 95% ; 96% ; 14" | pre-release | flows |  |
| 297 | "What this pass pins: a sensor with no…" | pre-release | flows |  |
| 298 | "A timestamp with no timezone is not a…" | pre-release | flows |  |
| 299 | "A job-id hint that is not text is…" | pre-release | flows |  |
| 300 | "Junk and unreadable times in the recent list…" | pre-release | flows |  |
| 301 | "An extension description with a newline is refused,…" | pre-release | flows |  |
| 302 | "A folder that cannot be stated is skipped." | pre-release | flows |  |
| 303 | "A baseline whose kinds are a list is…" | pre-release | flows |  |
| 304 | "A retained result that is a symlink is…" | pre-release | flows |  |
| 305 | "An alert that is not an object, and…" | pre-release | flows |  |
| 306 | "A chat id that is not JSON is…" | pre-release | flows |  |
| 307 | "A page-state that is not a map is…" | pre-release | flows |  |
| 308 | "A directory sitting in an answer slot is…" | pre-release | flows |  |
| 309 | "A late file with a broken line, a…" | pre-release | flows |  |
| 310 | "An empty outbox starts the deadline instead of…" | pre-release | flows |  |
| 311 | "Measured again the same day." | pre-release | flows |  |
| 312 | "4518 tests, OK, 22 skipped, 370 seconds." | pre-release | flows |  |
| 313 | "Statements: 16872." | pre-release | flows |  |
| 314 | "Missed: 618." | pre-release | flows |  |
| 315 | "Covered: 96.3%." | pre-release | flows |  |
| 316 | "Branches: 94.1%." | pre-release | flows |  |
| 317 | "Together: 95.7%." | pre-release | flows |  |
| 318 | "File ; Before this pass ; After ;…" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 319 | "runner.py ; 95.1% ; 95.6% ; 305" | pre-release | flows |  |
| 320 | "What this pass pins, in the on-disk job…" | pre-release | flows |  |
| 321 | "Our own pid is." | pre-release | flows |  |
| 322 | "A pid that is not running is not." | pre-release | flows |  |
| 323 | "A pid we are not allowed to signal…" | pre-release | flows |  |
| 324 | "Any other error from the signal is not…" | pre-release | flows |  |
| 325 | "Our own claim is not taken a second…" | pre-release | flows |  |
| 326 | "A claim we cannot read, and whose age…" | pre-release | flows |  |
| 327 | "A dead claim that cannot be unlinked stays,…" | pre-release | flows |  |
| 328 | "A claim file that cannot be created is…" | pre-release | flows |  |
| 329 | "Releasing a key that has no claim is…" | pre-release | flows |  |
| 330 | "Releasing does not delete a claim whose pid…" | pre-release | flows |  |
| 331 | "A release that cannot unlink our own claim…" | pre-release | flows |  |
| 332 | "The Windows pid check is still unrun." | pre-release | flows |  |
| 333 | "This tree is Linux." | pre-release | flows |  |
| 334 | "Measured again the same day." | pre-release | flows |  |
| 335 | "4527 tests, OK, 22 skipped, 372 seconds." | pre-release | flows |  |
| 336 | "Statements: 16872." | pre-release | flows |  |
| 337 | "Missed: 588." | pre-release | flows |  |
| 338 | "Covered: 96.5%." | pre-release | flows |  |
| 339 | "Branches: 94.3%." | pre-release | flows |  |
| 340 | "Together: 95.9%." | pre-release | flows |  |
| 341 | "File ; Before this pass ; After ;…" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 342 | "runner.py ; 95.6% ; 96.0% ; 275" | pre-release | flows |  |
| 343 | "What this pass pins, on the way into…" | pre-release | flows |  |
| 344 | "A job another process still holds stays unseen,…" | pre-release | flows |  |
| 345 | "On a version 2 message: a bad signature…" | pre-release | flows |  |
| 346 | "Cleartext is refused unless the process was started…" | pre-release | flows |  |
| 347 | "An answerer whose key is not on the…" | pre-release | flows |  |
| 348 | "A question whose deadline is out of range…" | pre-release | flows |  |
| 349 | "The answerer uses a model sentence when one…" | pre-release | flows |  |
| 350 | "A poll whose own IMAP logout throws, or…" | pre-release | flows |  |
| 351 | "An extension loader that throws is a warning." | pre-release | flows |  |
| 352 | "A registry that is not a map loads…" | pre-release | flows |  |
| 353 | "Measured again the same day, on the tree…" | pre-release | flows |  |
| 354 | "4549 tests, OK, 22 skipped, 367 seconds." | pre-release | flows |  |
| 355 | "Statements: 16872." | pre-release | flows |  |
| 356 | "Missed: 546." | pre-release | flows |  |
| 357 | "Covered: 96.8%." | pre-release | flows |  |
| 358 | "Branches: 94.5%." | pre-release | flows |  |
| 359 | "Together: 96.1%." | pre-release | flows |  |
| 360 | "File ; Before this pass ; After ;…" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 361 | "runner.py ; 96.0% ; 96.6% ; 236" | pre-release | flows |  |
| 362 | "The earlier 96.5% figure was taken before the…" | pre-release | flows |  |
| 363 | "This number includes that commit and this pass." | pre-release | flows |  |
| 364 | "What this pass pins: a version 2 message…" | pre-release | flows |  |
| 365 | "A determination is logged and not executed." | pre-release | flows |  |
| 366 | "A mail fetch that throws does not start…" | pre-release | flows |  |
| 367 | "With no transport extension there is nothing to…" | pre-release | flows |  |
| 368 | "A channel list that throws is a warning." | pre-release | flows |  |
| 369 | "A channel whose fetch throws is skipped." | pre-release | flows |  |
| 370 | "A channel message that is not version 2…" | pre-release | flows |  |
| 371 | "A remediation digest that does not name the…" | pre-release | flows |  |
| 372 | "A model lesson that throws, or that is…" | pre-release | flows |  |
| 373 | "Past the security-event cap, a chmod that fails…" | pre-release | flows |  |
