# Windows first run: papers to a real MCP tool call

This checks PenTwin on your own Windows PC. The final `check-mcp` command launches the local MCP server through stdio, discovers its tools, and invokes `corpus_status` and `generation_protocol`. It does not require an API key or send source passages to an LLM. It is a protocol test, not a ChatGPT Desktop installation or a claim that generated prose resembles its author.

## 1. Install the code

Install Python 3.11 or newer and Git for Windows. In PowerShell:

```powershell
git clone https://github.com/tasuku-kobayashi/PenTwin.git C:\src\PenTwin
cd C:\src\PenTwin
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

If `py -3.11` is unavailable but another Python 3.11+ is installed, create the environment with that Python executable instead. TeX input also requires `pandoc` on PATH; start with DOCX or text-selectable PDF if unavailable.

## 2. Place your papers privately

Create `C:\PenTwin-private\papers` outside the cloned repository. Put at least three **independent studies** by the same confirmed primary writer directly in that folder; no subfolders. Accepted extensions are `.pdf`, `.docx`, and `.tex`. Duplicate bytes are rejected, but the computer cannot tell whether different files describe the same study. For this short path, all files must have the same `published` or `unpublished` status.

Do not put any real paper, extracted text, manifest or run output in the public Git repository. A scanned PDF without selectable text may fail extraction.

## 3. Register and review

Use `unpublished` instead of `published` if all files are unpublished.

```powershell
.\.venv\Scripts\pentwin.exe onboard C:\PenTwin-private\papers C:\PenTwin-private\run-001 --status published --confirm-primary-writing --confirm-independent-studies
.\.venv\Scripts\pentwin.exe review C:\PenTwin-private\run-001
```

`onboard` creates anonymous paper IDs, `onboarding-manifest.json`, and `review.csv` in the private run. `review` displays each extracted passage and its original file/page or paragraph. Open that original yourself and check the text, order, headings, references, tables, and captions. For each passage:

1. Enter `n` to reject it, or `y` if it should contribute to the style profile.
2. After comparing an accepted passage with the original, type `verified` exactly.
3. Accept or correct the proposed section and choose its rhetorical move, such as `background`, `finding`, `interpretation` or `limitation`.
4. Enter `q` to pause; the same `review` command resumes unfinished rows. A failed verification also leaves the current row unfinished.

Only type `verified` for text you have actually compared with the original. The tool cannot infer primary writing or correct PDF extraction from a filename.

When `review` prints `"ready_to_seal": true`, run:

```powershell
.\.venv\Scripts\pentwin.exe seal C:\PenTwin-private\run-001
```

`seal` requires accepted passages from at least two development study families and one held-out study family. If there are none for a family, resume review or start a new private run with more suitable files. An existing sealed run is immutable. For mixed publication status, paper versions, or different writing contributions, use the manual `manifest.example.json` and `prepare` route in the README.

## 4. Call MCP tools for real

```powershell
.\.venv\Scripts\pentwin.exe check-mcp C:\PenTwin-private\run-001 --section discussion
```

Successful output includes `"mcp_connected": true`, `"sealed": true` inside `corpus_status`, a `tools` list containing `corpus_status` and `generation_protocol`, and `generation_conditions` containing `none` and `lexical`. An available plan is **not** proof of author likeness; the requested section can have insufficient evidence. If your reviewed passages were Introduction only, rerun with `--section introduction`.

For a live Claude Code conversation after this check, install Claude Code separately and register the same server:

```powershell
claude mcp add --transport stdio pentwin -- C:\src\PenTwin\.venv\Scripts\python.exe -m pentwin.cli serve C:\PenTwin-private\run-001
```

In Claude Code, inspect `/mcp` and ask it to call `corpus_status`. This is a separate client check; its results depend on the installed Claude Code version and configuration. ChatGPT Desktop local MCP plugin packaging and allowlisting have not been completed, so `check-mcp` does not establish that ChatGPT Desktop can see PenTwin. Do not paste the private run or unpublished passages into a public issue.
