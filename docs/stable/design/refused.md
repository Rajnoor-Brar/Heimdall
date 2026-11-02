---
id: refused
summary: what Heimdall deliberately does not do, and why
---

# What is refused

| Refused | Why |
|---|---|
| A general DAG or workflow engine | a chain is a sequence of groups; the connection rules only check it |
| Physics in TOML | it lives in the native card |
| An in-process event loop in the framework | V2; your own program may run one |
| Inferring connections, units, data maps, or which tool a quantity is for | a wrong guess looks plausible |
| Silently ignoring a key a backend or tool cannot honour | it is an error |
| Built-in statistics and fits | V4: a fit is a custom tool in `post` |
| Sharing events between points | V9: keep events as a `[prelim]` file instead |
| A C++ library layer | V7: a program links what it needs |
| CMake | V6: `make <path>.exe` is the interface |
