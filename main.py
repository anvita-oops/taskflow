from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import create_engine, Column, Integer, String, Enum, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from passlib.context import CryptContext
from jose import JWTError, jwt
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
import enum, os

# ─── DATABASE ───────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./taskflow.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ─── MODELS ─────────────────────────────────────────────────
class RoleEnum(str, enum.Enum):
    admin = "admin"
    member = "member"

class StatusEnum(str, enum.Enum):
    todo = "todo"
    in_progress = "in_progress"
    done = "done"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    memberships = relationship("ProjectMember", back_populates="user")
    tasks = relationship("Task", back_populates="assignee")

class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    members = relationship("ProjectMember", back_populates="project")
    tasks = relationship("Task", back_populates="project")

class ProjectMember(Base):
    __tablename__ = "project_members"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    project_id = Column(Integer, ForeignKey("projects.id"))
    role = Column(Enum(RoleEnum), default=RoleEnum.member)
    user = relationship("User", back_populates="memberships")
    project = relationship("Project", back_populates="members")

class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, default="")
    status = Column(Enum(StatusEnum), default=StatusEnum.todo)
    due_date = Column(DateTime, nullable=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    assignee_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    project = relationship("Project", back_populates="tasks")
    assignee = relationship("User", back_populates="tasks")

Base.metadata.create_all(bind=engine)

# ─── AUTH ────────────────────────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "changethiskey123")
ALGORITHM = "HS256"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")

def hash_pw(pw): return pwd_context.hash(pw)
def verify_pw(plain, hashed): return pwd_context.verify(plain, hashed)
def make_token(user_id: int):
    exp = datetime.utcnow() + timedelta(hours=24)
    return jwt.encode({"sub": str(user_id), "exp": exp}, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
    except (JWTError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

# ─── SCHEMAS ─────────────────────────────────────────────────
class SignupIn(BaseModel):
    name: str
    email: str
    password: str

class LoginIn(BaseModel):
    email: str
    password: str

class ProjectIn(BaseModel):
    name: str
    description: Optional[str] = ""

class TaskIn(BaseModel):
    title: str
    description: Optional[str] = ""
    status: Optional[str] = "todo"
    assignee_id: Optional[int] = None
    due_date: Optional[str] = None

class AddMemberIn(BaseModel):
    user_id: int
    role: Optional[str] = "member"

# ─── APP ─────────────────────────────────────────────────────
app = FastAPI(title="TaskFlow")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], allow_credentials=True)
@app.get("/")
def home():
    return {"message": "TaskFlow API Running"}


# ─── AUTH ROUTES ─────────────────────────────────────────────
@app.post("/api/signup")
def signup(data: SignupIn, db: Session = Depends(get_db)):
    if len(data.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(400, "Email already registered")
    user = User(name=data.name, email=data.email, hashed_password=hash_pw(data.password))
    db.add(user); db.commit(); db.refresh(user)
    return {"token": make_token(user.id), "user": {"id": user.id, "name": user.name, "email": user.email}}

@app.post("/api/login")
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_pw(data.password, user.hashed_password):
        raise HTTPException(401, "Invalid email or password")
    return {"token": make_token(user.id), "user": {"id": user.id, "name": user.name, "email": user.email}}

@app.get("/api/me")
def me(u: User = Depends(get_current_user)):
    return {"id": u.id, "name": u.name, "email": u.email}

@app.get("/api/users")
def all_users(db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    return [{"id": x.id, "name": x.name, "email": x.email} for x in db.query(User).all()]

# ─── DASHBOARD ───────────────────────────────────────────────
@app.get("/api/dashboard")
def dashboard(db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    pids = [m.project_id for m in db.query(ProjectMember).filter_by(user_id=u.id).all()]
    tasks = db.query(Task).filter(Task.project_id.in_(pids)).all()
    now = datetime.utcnow()
    return {
        "total": len(tasks),
        "todo": sum(1 for t in tasks if t.status == "todo"),
        "in_progress": sum(1 for t in tasks if t.status == "in_progress"),
        "done": sum(1 for t in tasks if t.status == "done"),
        "overdue": sum(1 for t in tasks if t.due_date and t.due_date < now and t.status != "done"),
        "my_tasks": [{"id": t.id, "title": t.title, "status": t.status,
                      "due_date": str(t.due_date)[:10] if t.due_date else None,
                      "project": t.project.name}
                     for t in tasks if t.assignee_id == u.id]
    }

# ─── PROJECT ROUTES ──────────────────────────────────────────
@app.get("/api/projects")
def list_projects(db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    memberships = db.query(ProjectMember).filter_by(user_id=u.id).all()
    result = []
    for m in memberships:
        p = m.project
        tc = len(p.tasks)
        dc = sum(1 for t in p.tasks if t.status == "done")
        result.append({"id": p.id, "name": p.name, "description": p.description,
                        "role": m.role, "task_count": tc, "done_count": dc})
    return result

@app.post("/api/projects")
def create_project(data: ProjectIn, db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    if not data.name.strip():
        raise HTTPException(400, "Project name required")
    p = Project(name=data.name, description=data.description)
    db.add(p); db.commit(); db.refresh(p)
    db.add(ProjectMember(user_id=u.id, project_id=p.id, role=RoleEnum.admin))
    db.commit()
    return {"id": p.id, "name": p.name, "description": p.description, "role": "admin"}

@app.get("/api/projects/{pid}")
def get_project(pid: int, db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    m = db.query(ProjectMember).filter_by(project_id=pid, user_id=u.id).first()
    if not m: raise HTTPException(403, "Not a member")
    p = m.project
    return {"id": p.id, "name": p.name, "description": p.description, "role": m.role,
            "members": [{"user_id": x.user_id, "name": x.user.name, "email": x.user.email, "role": x.role} for x in p.members]}

@app.post("/api/projects/{pid}/members")
def add_member(pid: int, data: AddMemberIn, db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    me = db.query(ProjectMember).filter_by(project_id=pid, user_id=u.id).first()
    if not me or me.role != RoleEnum.admin: raise HTTPException(403, "Admins only")
    if db.query(ProjectMember).filter_by(project_id=pid, user_id=data.user_id).first():
        raise HTTPException(400, "Already a member")
    db.add(ProjectMember(user_id=data.user_id, project_id=pid, role=data.role))
    db.commit()
    return {"message": "Added"}

@app.delete("/api/projects/{pid}/members/{uid}")
def remove_member(pid: int, uid: int, db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    me = db.query(ProjectMember).filter_by(project_id=pid, user_id=u.id).first()
    if not me or me.role != RoleEnum.admin: raise HTTPException(403, "Admins only")
    m = db.query(ProjectMember).filter_by(project_id=pid, user_id=uid).first()
    if not m: raise HTTPException(404, "Not found")
    db.delete(m); db.commit()
    return {"message": "Removed"}

# ─── TASK ROUTES ─────────────────────────────────────────────
@app.get("/api/projects/{pid}/tasks")
def list_tasks(pid: int, db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    if not db.query(ProjectMember).filter_by(project_id=pid, user_id=u.id).first():
        raise HTTPException(403, "Not a member")
    tasks = db.query(Task).filter_by(project_id=pid).all()
    return [{"id": t.id, "title": t.title, "description": t.description, "status": t.status,
             "due_date": str(t.due_date)[:10] if t.due_date else None,
             "assignee": {"id": t.assignee.id, "name": t.assignee.name} if t.assignee else None}
            for t in tasks]

@app.post("/api/projects/{pid}/tasks")
def create_task(pid: int, data: TaskIn, db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    if not db.query(ProjectMember).filter_by(project_id=pid, user_id=u.id).first():
        raise HTTPException(403, "Not a member")
    if not data.title.strip(): raise HTTPException(400, "Title required")
    due = datetime.fromisoformat(data.due_date) if data.due_date else None
    t = Task(title=data.title, description=data.description, project_id=pid,
             assignee_id=data.assignee_id, due_date=due, status=data.status or "todo")
    db.add(t); db.commit(); db.refresh(t)
    return {"id": t.id, "title": t.title, "status": t.status}

@app.put("/api/projects/{pid}/tasks/{tid}")
def update_task(pid: int, tid: int, data: TaskIn, db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    if not db.query(ProjectMember).filter_by(project_id=pid, user_id=u.id).first():
        raise HTTPException(403, "Not a member")
    t = db.query(Task).filter_by(id=tid, project_id=pid).first()
    if not t: raise HTTPException(404, "Task not found")
    t.title = data.title; t.description = data.description; t.status = data.status
    t.assignee_id = data.assignee_id
    if data.due_date: t.due_date = datetime.fromisoformat(data.due_date)
    db.commit()
    return {"message": "Updated"}

@app.delete("/api/projects/{pid}/tasks/{tid}")
def delete_task(pid: int, tid: int, db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    me = db.query(ProjectMember).filter_by(project_id=pid, user_id=u.id).first()
    if not me or me.role != RoleEnum.admin: raise HTTPException(403, "Admins only")
    t = db.query(Task).filter_by(id=tid, project_id=pid).first()
    if not t: raise HTTPException(404, "Not found")
    db.delete(t); db.commit()
    return {"message": "Deleted"}