# Project Specification

## Overview

The system is an internal project management and payment tracking platform.

Main goals:
- Manage projects
- Manage suppliers and users
- Track project items (nomenclature)
- Create and manage payment requests
- Track incoming payments
- Provide role-based access (admin / client)
- Send notifications via Telegram bot

---

## Authentication & Roles

### Roles

#### Admin
- Full access to all system features
- Can create, edit, delete:
  - suppliers
  - users
  - projects
  - project items (nomenclature)
  - payment requests
  - payments
- Sees all financial data including cost and profit

#### Client
- Limited access
- Can:
  - view only assigned projects
  - view payment requests
  - add/delete payments for requests
- Cannot:
  - create/edit/delete projects
  - add/edit nomenclature
  - create payment requests
- Restrictions:
  - cannot see cost price
  - cannot see profit

---

## Main Sections

### 1. Authentication
- Standard login page (login + password)

---

### 2. Main Page

After login:

- Admin:
  - access to:
    - Database
    - Projects

- Client:
  - access ONLY to:
    - Projects
  - automatic redirect to Projects page

---

## Database Section

### Suppliers

Fields:
- id (internal)
- full_name (required)
- phone (required)
- wechat_id (required)
- document_1
- document_2
- document_3
- description

Features:
- create supplier
- edit supplier
- delete supplier
- view supplier details

---

### Users

Fields:
- id
- full_name
- login
- password
- role (admin / client)
- description

Features:
- create user
- edit user
- delete user

---

## Projects Section

### Project List

- Display as cards
- Sorted by creation date (new → old)
- Filters:
  - active
  - closed

Fields:
- id (auto)
- name
- description
- created_at (auto)
- client (selected from users)
- status (active / closed)

Access:
- Admin → sees all projects
- Client → sees only assigned projects

---

## Project Detail Page

Contains:

### Left (1/3): Nomenclature (Project Items)

Each item:

- name
- details
- quantity
- supplier (from suppliers DB)
- price
- cost_price
- currency (CNY / USD / RUB)
- commission
- requirements (max 5, added over time)

Features:
- add item
- edit item
- delete item

Display (table):
- name
- quantity

Click → full detail view

Restrictions:
- Client:
  - sees price
  - DOES NOT see cost_price

---

### Calculations (Bottom of Nomenclature)

- total = sum(price * quantity)
- remaining = total - paid_amount
- profit = sum((price - cost_price) * quantity)

Restrictions:
- Client:
  - cannot see profit

---

### Right (2/3): Payment Requests

---

## Payment Request

Created from project items

Fields:
- selected items
- amount per item
- total amount
- requisites
- payment details
- attachments (max 3 files)

After creation:
- stored in system
- visible in project page

Display:
- items (comma-separated)
- total amount
- remaining amount

Actions:
- view
- edit
- delete
- copy info (items + requisites)
- add payment

---

## Payments

Each payment:

- amount
- file (attachment)
- note

After adding:
- reduces remaining amount of request

Features:
- add payment
- delete payment

Goal:
- request is complete when remaining = 0

---

## Project Deletion Rule

- Project can be deleted ONLY if:
  - it has NO payment requests

---

## Telegram Bot

### Notifications

Client:
- receives notification when payment request is created

Admin:
- receives notification when payment is added

Message:
- full request info
- link to request

---

## Access Rules Summary

### Admin
- full control
- full visibility

### Client
- read-only access (except payments)
- sees only assigned projects
- cannot:
  - create/edit/delete projects
  - manage suppliers/users
  - manage nomenclature
  - create payment requests
- can:
  - view payment requests
  - add/delete payments

---

## System Requirements

- Role-based access control
- File uploads
- Calculations:
  - totals
  - remaining balances
  - profit
- Clean UI for:
  - tables
  - cards
  - forms
- Telegram integration