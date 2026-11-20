# Security policy

## Supported versions

Only the latest build on `main` gets fixes. The current version is
`IP_VERSION` in the [Makefile](Makefile).

## Scope

This project runs on a Sega Saturn and on the developer's own machine. It has
no servers, accounts or network code. Security reports that fit this project:

- A build or bootstrap script that runs untrusted code, writes outside the
  repository, or fetches a source without checking its pinned revision
  (`sources.lock.json`).
- A tracked file that holds SEGA data, a BIOS, a disc image, a credential or
  other private data.
- A dependency fetched by `tools/bootstrap.sh` with a known vulnerability that
  affects the host build.

Game bugs and crashes on the Saturn are not security issues. Open a normal
[bug report](https://github.com/t3chnaztea/sonic-cd-saturn/issues/new/choose).

## Reporting

Do not open a public issue. Report privately through
[GitHub private vulnerability reporting](https://github.com/t3chnaztea/sonic-cd-saturn/security/advisories/new).
Include the affected file, the commit, and the steps to reproduce. Do not
attach disc images, BIOS files, built images or game data.

The maintainer is one person working in spare time. There is no fixed
response time and no bug bounty.
