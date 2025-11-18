 # django-legal

**django-legal** is a lightweight Django app designed to manage legal documents and track user acceptance of the current legal conditions required to use a site.

This project is currently in **active development**.  
The goal of the MVP is to provide a simple, reliable foundation for handling legal documents, versioning, and acceptance—without enforcing any design choices, UI frameworks, or authentication libraries.

---

## Purpose of the App

Many websites need users to agree to one or more legal documents such as:

- Terms of Use
- Privacy Policy
- Refund Policy
- Cookies Policy
- Service Agreements

**django-legal** provides a minimal, flexible way to:

- Create and manage these legal documents
- Automatically version documents when changes are made
- Store a hash for each published version
- Record which versions each user has accepted
- Restrict access to certain views until all required documents are accepted

The emphasis is on **simplicity**, **auditability**, and **developer freedom**.

---

## MVP Behaviour

The MVP focuses on one core task:

> **Ensure that authenticated users accept the latest versions of required legal documents before accessing protected views.**

The app will provide:

### 1. Document & Version Management

- Create legal documents in the Django admin
- Mark documents as “required”
- Publish new versions
- Each new version is immutable and automatically hashed
- Versions use a simple diff-based auto-incremented `X.Y.Z` system

### 2. User Acceptance Tracking

- Acceptances are tied to authenticated users
- Each acceptance stores the version and its hash
- Every new version requires re-acceptance
- Old versions are never edited or removed

### 3. View Protection

- A `@legal` decorator that checks whether the user has accepted all current required documents
- If not, the user is redirected to a configurable “legal acceptance” page

### 4. Minimal Templates

- The package will ship with simple example templates
- Developers can override or replace these templates to match their own site
- The app does not dictate any specific styling or UX patterns

---

## Basic Usage Flow (for developers)

Once the project reaches its first release, integrating **django-legal** into a Django project will look roughly like this:

1. **Install django-legal** (from PyPI or your chosen source).
2. **Ensure the project has an authentication system**  
   (django-legal requires logged-in users for acceptance).
3. **Connect authentication to django-legal**  
   (the MVP will support the built-in Django user model by default).
4. **Use Django admin to create legal documents**:
   - Add content  
   - Publish versions  
   - Mark which documents are required
5. **Protect sensitive or important views** using the `@legal` decorator.
6. **Create a page for users to review and accept required documents**  
   using your own UI or by extending the app’s basic templates.
7. From that point on, **any new version of a legal document will be automatically created, hashed, versioned, and will require re-acceptance**.

---

## Project Status

This is the **initial development phase** of **django-legal**.  
Features and APIs are still being shaped, and documentation will expand as the project evolves.

Once the first stable version is ready, this README will be updated with:

- Installation instructions
- Configuration guides
- Template override examples



