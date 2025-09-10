# CLAUDE.md - Amazon Product Monitoring Tool

> **Documentation Version**: 1.0  
> **Last Updated**: 2025-01-10  
> **Project**: Amazon Product Monitoring Tool  
> **Description**: FastAPI backend for Amazon product tracking and competitive analysis  
> **Features**: GitHub auto-backup, Task agents, technical debt prevention

✅ CRITICAL RULES ACKNOWLEDGED - I will follow all prohibitions and requirements listed in CLAUDE.md

This file provides essential guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 🚨 CRITICAL RULES - READ FIRST

> **⚠️ RULE ADHERENCE SYSTEM ACTIVE ⚠️**  
> **Claude Code must explicitly acknowledge these rules at task start**  
> **These rules override all other instructions and must ALWAYS be followed:**

### 🔄 **RULE ACKNOWLEDGMENT REQUIRED**
> **Before starting ANY task, Claude Code must respond with:**  
> "✅ CRITICAL RULES ACKNOWLEDGED - I will follow all prohibitions and requirements listed in CLAUDE.md"

### ❌ ABSOLUTE PROHIBITIONS
- **NEVER** create new files in root directory → use proper module structure
- **NEVER** write output files directly to root directory → use designated output folders
- **NEVER** create documentation files (.md) unless explicitly requested by user
- **NEVER** use git commands with -i flag (interactive mode not supported)
- **NEVER** use `find`, `grep`, `cat`, `head`, `tail`, `ls` commands → use Read, LS, Grep, Glob tools instead
- **NEVER** create duplicate files (manager_v2.py, enhanced_xyz.py, utils_new.js) → ALWAYS extend existing files
- **NEVER** create multiple implementations of same concept → single source of truth
- **NEVER** copy-paste code blocks → extract into shared utilities/functions
- **NEVER** hardcode values that should be configurable → use config files/environment variables
- **NEVER** use naming like enhanced_, improved_, new_, v2_ → extend original files instead

### 📝 MANDATORY REQUIREMENTS
- **COMMIT** after every completed task/phase - no exceptions
- **GITHUB BACKUP** - Push to GitHub after every commit to maintain backup: `git push origin main`
- **USE TASK AGENTS** for all long-running operations (>30 seconds) - Bash commands stop when context switches
- **TODOWRITE** for complex tasks (3+ steps) → parallel agents → git checkpoints → test validation
- **READ FILES FIRST** before editing - Edit/Write tools will fail if you didn't read the file first
- **DEBT PREVENTION** - Before creating new files, check for existing similar functionality to extend  
- **SINGLE SOURCE OF TRUTH** - One authoritative implementation per feature/concept
- **DEPENDENCY-GATE**: Before any step that would require installed packages, **pause** and wait for user's `continue` after showing the dependency list.

### ⚡ EXECUTION PATTERNS
- **PARALLEL TASK AGENTS** - Launch multiple Task agents simultaneously for maximum efficiency
- **SYSTEMATIC WORKFLOW** - TodoWrite → Parallel agents → Git checkpoints → GitHub backup → Test validation
- **GITHUB BACKUP WORKFLOW** - After every commit: `git push origin main` to maintain GitHub backup
- **BACKGROUND PROCESSING** - ONLY Task agents can run true background operations

### ⏸️ Wait-for-Continue Gates
Introduce gates at these milestones:
- After **dependency listing**
- After **test scaffolding**
- Before **running long/irreversible ops** (migrations, data writes, releases)
Prompt format (standardized):
> "**PAUSED**: [reason]. Perform the manual step, then reply `continue` to proceed, or paste errors for me to fix."


### 🧩 Package & Environment Safety
- **NEVER** auto-install dependencies. When dependencies are needed, **ONLY**:
  1) Generate a dependency list (e.g., `docs/dependencies.md` and `requirements.txt` for Python)  
  2) Show the list to the user and **STOP** with the prompt:  
     **"Dependencies listed only. Please install manually. Type `continue` when ready."**
- **WAIT FOR `continue`**: Do not proceed with any next step until the user explicitly replies `continue`.
- **Lockfiles**: If a lockfile is applicable (e.g., `requirements.txt`/`poetry.lock`, `package-lock.json`/`pnpm-lock.yaml`), **only generate** (do not install).

### 🧪 Virtual Environment Enforcement
- **ALWAYS** activate the project's virtual environment **before any command** (Bash/Task agent).
- Ask once during setup: **"Where is your virtual environment?** (options: create `.venv` here / path provided / conda env name)"  
- **Never** assume a global interpreter. Respect user's Python/Node/… version.
- Command wrapper pattern (pseudo):
  - macOS/Linux (Python): `source .venv/bin/activate && <command>`
  - Windows PowerShell: `.venv\\Scripts\\Activate.ps1; <command>`
  - Conda: `conda activate <env-name> && <command>`

### 🧪 Testing Policy
- **ALWAYS** scaffold tests (`tests/` or `src/test/unit|integration|fixtures`) together with features.
- **DO NOT** auto-run tests. After generating test files, **STOP** and display:
  > "Tests generated but not executed. Please run them manually.  
  > After running, either paste failing logs for me to fix, or type `continue` to proceed."
- Include **sample commands** only (not executed):
  - Python: `pytest -q` or `python -m pytest -q`
  - Node: `npm test` / `pnpm test` / `yarn test`
- Keep tests **hermetic** (mock I/O, avoid network); provide fixtures under `tests/fixtures/`.

### 🔍 MANDATORY PRE-TASK COMPLIANCE CHECK
> **STOP: Before starting any task, Claude Code must explicitly verify ALL points:**

**Step 0: Dependency Gate**
- [ ] Dependencies have been **listed** (not installed) and user has been prompted to install manually
- [ ] User replied **`continue`** after manual installation

**Step 1: Gather Project Info**
- [ ] User clarified goals, inputs, outputs

**Step 2: Environment Check**
- [ ] Is a virtual environment **active**? → If NO, prompt for venv and **activate before proceeding**

**Step 3: Rule Acknowledgment**
- [ ] ✅ I acknowledge all critical rules in CLAUDE.md and will follow them

**Step 4: Task Analysis**  
- [ ] Will this create files in root? → If YES, use proper module structure instead
- [ ] Will this take >30 seconds? → If YES, use Task agents not Bash
- [ ] Is this 3+ steps? → If YES, use TodoWrite breakdown first
- [ ] Am I about to use grep/find/cat? → If YES, use proper tools instead

**Step 5: Technical Debt Prevention (MANDATORY SEARCH FIRST)**
- [ ] **SEARCH FIRST**: Use Grep pattern="<functionality>.*<keyword>" to find existing implementations
- [ ] **CHECK EXISTING**: Read any found files to understand current functionality
- [ ] Does similar functionality already exist? → If YES, extend existing code
- [ ] Am I creating a duplicate class/manager? → If YES, consolidate instead
- [ ] Will this create multiple sources of truth? → If YES, redesign approach
- [ ] Have I searched for existing implementations? → Use Grep/Glob tools first
- [ ] Can I extend existing code instead of creating new? → Prefer extension over creation
- [ ] Am I about to copy-paste code? → Extract to shared utility instead

**Step 6: Session Management**
- [ ] Is this a long/complex task? → If YES, plan context checkpoints
- [ ] Have I been working >1 hour? → If YES, consider /compact or session break

> **⚠️ DO NOT PROCEED until all checkboxes are explicitly verified**

## 🐙 GITHUB SETUP & AUTO-BACKUP

> **🤖 FOR CLAUDE CODE: When initializing any project, automatically ask about GitHub setup**

### 🎯 **GITHUB SETUP PROMPT** (AUTOMATIC)
> **⚠️ CLAUDE CODE MUST ALWAYS ASK THIS QUESTION when setting up a new project:**

```
🐙 GitHub Repository Setup
Would you like to set up a remote GitHub repository for this project?

Options:
1. ✅ YES - Create new GitHub repo and enable auto-push backup
2. ✅ YES - Connect to existing GitHub repo and enable auto-push backup  
3. ❌ NO - Skip GitHub setup (local git only)

[Wait for user choice before proceeding]
```

### 🚀 **OPTION 1: CREATE NEW GITHUB REPO**
If user chooses to create new repo, execute:

```bash
# Ensure GitHub CLI is available
gh --version || echo "⚠️ GitHub CLI (gh) required. Install: brew install gh"

# Authenticate if needed
gh auth status || gh auth login

# Create new GitHub repository
echo "Enter repository name (or press Enter for current directory name):"
read repo_name
repo_name=${repo_name:-$(basename "$PWD")}

# Create repository
gh repo create "$repo_name" --public --description "Project managed with Claude Code" --confirm

# Add remote and push
git remote add origin "https://github.com/$(gh api user --jq .login)/$repo_name.git"
git branch -M main
git push -u origin main

echo "✅ GitHub repository created and connected: https://github.com/$(gh api user --jq .login)/$repo_name"
```

### 🔗 **OPTION 2: CONNECT TO EXISTING REPO**
If user chooses to connect to existing repo, execute:

```bash
# Get repository URL from user
echo "Enter your GitHub repository URL (https://github.com/username/repo-name):"
read repo_url

# Extract repo info and add remote
git remote add origin "$repo_url"
git branch -M main
git push -u origin main

echo "✅ Connected to existing GitHub repository: $repo_url"
```

### 🔄 **AUTO-PUSH CONFIGURATION**
For both options, configure automatic backup:

```bash
# Create git hook for auto-push (optional but recommended)
cat > .git/hooks/post-commit << 'EOF'
#!/bin/bash
# Auto-push to GitHub after every commit
echo "🔄 Auto-pushing to GitHub..."
git push origin main
if [ $? -eq 0 ]; then
    echo "✅ Successfully backed up to GitHub"
else
    echo "⚠️ GitHub push failed - manual push may be required"
fi
EOF

chmod +x .git/hooks/post-commit

echo "✅ Auto-push configured - GitHub backup after every commit"
```

### 📋 **GITHUB BACKUP WORKFLOW** (MANDATORY)
> **⚠️ CLAUDE CODE MUST FOLLOW THIS PATTERN:**

```bash
# After every commit, always run:
git push origin main

# This ensures:
# ✅ Remote backup of all changes
# ✅ Collaboration readiness  
# ✅ Version history preservation
# ✅ Disaster recovery protection
```

### 🛡️ **GITHUB REPOSITORY SETTINGS** (AUTO-CONFIGURED)
When repository is created, these settings are applied:

- **Default Branch**: `main` (modern standard)
- **Visibility**: Public (can be changed later)
- **Auto-merge**: Disabled (manual approval required)
- **Branch Protection**: Recommended for collaborative projects
- **Issues & Wiki**: Enabled for project management

### 🎯 **CLAUDE CODE GITHUB COMMANDS**
Essential GitHub operations for Claude Code:

```bash
# Check GitHub connection status
gh auth status && git remote -v

# Create new repository (if needed)
gh repo create [repo-name] --public --confirm

# Push changes (after every commit)
git push origin main

# Check repository status
gh repo view

# Clone repository (for new setup)
gh repo clone username/repo-name
```

## 🏗️ PROJECT OVERVIEW

Amazon Product Monitoring Tool - FastAPI backend for product tracking and competitive analysis with Supabase PostgreSQL, Redis caching, Celery workers, and comprehensive observability.

### 🎯 **DEVELOPMENT STATUS**
- **Setup**: Folder structure complete, design docs ready
- **Core Features**: Pending implementation
- **Testing**: Test strategy documented
- **Documentation**: Architecture and API design complete

## 📋 NEED HELP? START HERE

- Read `docs/ARCHITECTURE.md` for system overview
- Check `docs/API_DESIGN.md` for endpoint specifications
- Review `docs/DATABASE_DESIGN.md` for schema details
- See `docs/PROJECT_PLAN.md` for implementation roadmap

## 🎯 RULE COMPLIANCE CHECK

Before starting ANY task, verify:
- [ ] ✅ I acknowledge all critical rules above
- [ ] Files go in proper module structure (not root)
- [ ] Use Task agents for >30 second operations
- [ ] TodoWrite for 3+ step tasks
- [ ] Commit after each completed task

## 🚀 COMMON COMMANDS

```bash
# Activate virtual environment
pyenv activate amazon

# Run API server
uvicorn src.main.app:app --reload --host 0.0.0.0 --port 8000

# Run Celery worker
celery -A src.main.tasks worker --loglevel=INFO

# Run Celery beat scheduler  
celery -A src.main.tasks beat --loglevel=INFO

# Run tests
pytest src/test/

# Start Redis (Docker)
docker run -d --name redis -p 6379:6379 redis:7
```

## 🚨 TECHNICAL DEBT PREVENTION

### ❌ WRONG APPROACH (Creates Technical Debt):
```bash
# Creating new file without searching first
Write(file_path="new_feature.py", content="...")
```

### ✅ CORRECT APPROACH (Prevents Technical Debt):
```bash
# 1. SEARCH FIRST
Grep(pattern="feature.*implementation", include="*.py")
# 2. READ EXISTING FILES  
Read(file_path="existing_feature.py")
# 3. EXTEND EXISTING FUNCTIONALITY
Edit(file_path="existing_feature.py", old_string="...", new_string="...")
```

## 🧹 DEBT PREVENTION WORKFLOW

### Before Creating ANY New File:
1. **🔍 Search First** - Use Grep/Glob to find existing implementations
2. **📋 Analyze Existing** - Read and understand current patterns
3. **🤔 Decision Tree**: Can extend existing? → DO IT | Must create new? → Document why
4. **✅ Follow Patterns** - Use established project patterns
5. **📈 Validate** - Ensure no duplication or technical debt

---

**⚠️ Prevention is better than consolidation - build clean from the start.**  
**🎯 Focus on single source of truth and extending existing functionality.**  
**📈 Each task should maintain clean architecture and prevent technical debt.**