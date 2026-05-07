# TaskFlow

A simple project management web app where users can:
- Sign up and log in
- Create projects
- Assign tasks
- Track task progress
- Manage teams with role-based access (Admin/Member)

---

# Features

## Authentication
- User Signup
- User Login
- JWT Authentication

## Project Management
- Create Projects
- Add Members
- View Projects

## Task Management
- Create Tasks
- Assign Tasks
- Update Task Status
- Delete Tasks

## Dashboard
- Total Tasks
- Completed Tasks
- Pending Tasks
- Overdue Tasks

---

# Tech Stack

## Frontend
- HTML
- CSS
- JavaScript

## Backend
- FastAPI (Python)

## Database
- MySQL

## Deployment
- Railway (Backend)
- Vercel (Frontend)

---

# Live URLs

## Frontend
PASTE_YOUR_VERCEL_URL

## Backend API
https://web-production-40ecb.up.railway.app

## API Docs
https://web-production-40ecb.up.railway.app/docs

---

# GitHub Repository

PASTE_YOUR_GITHUB_REPO_LINK

---

# API Endpoints

## Auth
- POST /api/signup
- POST /api/login

## Projects
- GET /api/projects
- POST /api/projects

## Tasks
- GET /api/projects/{id}/tasks
- POST /api/projects/{id}/tasks
- PUT /api/projects/{id}/tasks/{taskId}
- DELETE /api/projects/{id}/tasks/{taskId}

---

# How To Run Locally

## Clone Repository

```bash
git clone YOUR_GITHUB_REPO_LINK
