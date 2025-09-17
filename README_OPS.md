# StegVerse-SCW — Ops & Recovery Guide

This document explains how to operate, recover, and redeploy the **SCW** (Sandbox Code Writer) stack:
- **API** (FastAPI)
- **UI** (Next.js)
- **Worker** (queue processor; Redis-backed)
- **Edge/site providers** (Cloudflare, Netlify, Vercel)
- The **Admin Token** lifecycle (bootstrap → normal ops → recovery)
- The **One-Click Reset & Redeploy** flow

---

## Contents
- [Architecture Overview](#architecture-overview)
- [Security Model](#security-model)
- [Environment & Config Keys](#environment--config-keys)
- [Endpoints (Ops API)](#endpoints-ops-api)
- [Diagnostics Page (`/diag.html`)](#diagnostics-page-diaghtml)
- [Common Flows](#common-flows)
  - [First-time Bootstrap](#first-time-bootstrap)
  - [Normal Operations](#normal-operations)
  - [Lost Admin Token (Recovery)](#lost-admin-token-recovery)
  - [One-Click Reset & Redeploy](#one-click-reset--redeploy)
  - [Worker State Reset](#worker-state-reset)
  - [Cloudflare Rotate/Purge](#cloudflare-rotatepurge)
- [Curl Cheat Sheet](#curl-cheat-sheet)
- [Troubleshooting](#troubleshooting)
- [Operational Checklists](#operational-checklists)
- [Addendum: Repo Pointers & UI Autodetect](#addendum-repo-pointers--ui-autodetect)

---

## Architecture Overview
