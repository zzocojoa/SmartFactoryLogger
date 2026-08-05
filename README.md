# Smart Factory Logger Project

This repository manages the Smart Factory Logger application, supporting both
the legacy Tkinter version and the next-generation Web Tech version.

## Project Structure

### 📂 [v1_legacy](./v1_legacy/README.md)

**Status**: Stable (Maintenance Mode)\
**Tech Stack**: Python, Tkinter\
The original desktop application currently running in production. Use this for
hotfixes and stable deployment.

**Execution**:

```bash
cd v1_legacy
python src/main.py
```

### 📂 [v2_next](./v2_next/README.md)

**Status**: In Development (Implementation Phase)\
**Tech Stack**: Python (FastAPI), React, Electron\
The next-generation version featuring a flexible web-based dashboard and remote
monitoring capabilities.

**Documentation**:

- [V2 development and validation guide](./v2_next/README.md)
- [V2 deployment checklist](./v2_next/docs/V2/DEPLOYMENT_CHECKLIST.md)
- [Backend API reference](./v2_next/backend/API_DOCUMENTATION.md)
- [SPOT source-port validation report](./v2_next/docs/04-report/spot-tcp-source-port-quarantine-v2.report.md)
