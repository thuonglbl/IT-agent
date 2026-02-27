# PRD: GLPI LDAP User Import - Investigation & Resolution

**Document ID:** PRD-LDAP-001
**Created:** 2026-02-27
**Status:** Completed
**Priority:** High

---

## 1. Problem Statement

GLPI's LDAP import was only retrieving ~1,000 users from Active Directory, while the organization has significantly more employees. This resulted in a large number of missing user accounts in GLPI, directly impacting:

- Ticket assignment (cannot assign to missing users)
- User authentication (missing users cannot log in via LDAP)
- Reporting accuracy (incomplete user base)
- Migration integrity (Jira-to-GLPI ticket migration relies on user matching)

---

## 2. Environment

| Component | Detail |
|-----------|--------|
| **GLPI Instance** | On-premise GLPI |
| **LDAP Server** | Microsoft Active Directory (on-premise) |
| **Port** | 389 (plain LDAP) |
| **BaseDN** | Root domain DN (e.g., `DC=example,DC=local`) |
| **Bind Account** | Dedicated LDAP service account |
| **Login Field** | `samaccountname` |
| **Sync Field** | `objectguid` |

---

## 3. Root Cause Analysis

### Primary Cause: Active Directory MaxPageSize Limit

Microsoft Active Directory enforces a default **MaxPageSize = 1,000** policy on LDAP queries. When GLPI sends a non-paged LDAP query, AD silently truncates the result set to the first 1,000 entries.

**Before fix:**
- GLPI `Use paged results = No`
- GLPI sends single LDAP query → AD returns max 1,000 users → remaining users invisible
- "Import New Users" page shows "No results found" because all 1,000 returned users were already imported

### Contributing Factors:
- Connection filter did not exclude disabled accounts, inflating results with inactive users
- Entity LDAP configuration was pointing to a local server instead of the Default Server
- Low timeout (10s) risked incomplete results on large queries

---

## 4. Solution Applied

### 4.1 LDAP Directory Configuration Changes

**Path:** Setup > Authentication > LDAP Directories > \<directory name\>

| Setting | Before | After | Reason |
|---------|--------|-------|--------|
| **Connection Filter** | `(&(objectCategory=person)(objectclass=user))` | `(&(objectClass=user)(objectCategory=person))` | Keep disabled accounts included — they are still assigned to Jira tickets and must exist in GLPI for migration user matching |
| **Use paged results** | No | **Yes** | Enable LDAP paging (RFC 2696) to bypass AD's 1,000-entry MaxPageSize limit |
| **Page Size** | 100 | **10000** | Larger page size reduces number of round-trips for large directories |
| **Timeout** | 10 | **30** | Allow more time for paged queries across large user base |

### 4.2 Entity LDAP Configuration Change

**Path:** Administration > Entities > \<entity name\> > Advanced Information

| Setting | Before | After | Reason |
|---------|--------|-------|--------|
| **LDAP Directory** | Local server | **Default Server** | Ensure entity uses the correctly configured LDAP directory with paged results enabled |

---

## 5. Technical Details

### 5.1 Connection Filter Explained

```
(&
  (objectClass=user)                                          # Must be a user object
  (objectCategory=person)                                     # Must be a person (not computer/service)
)
```

> **Why keep disabled accounts?** Disabled AD accounts (e.g., former employees) may still be assigned to Jira tickets being migrated to GLPI. Excluding them via `(!(userAccountControl:1.2.840.113556.1.4.803:=2))` would cause user matching failures during migration. Import all users first, then manage inactive accounts in GLPI after migration is complete.

### 5.2 LDAP Paging (RFC 2696)

When `Use paged results = Yes`:
1. GLPI sends LDAP query with Simple Paged Results Control
2. AD returns first page (up to Page Size entries) + a cookie
3. GLPI sends next request with the cookie
4. Repeats until AD returns empty cookie (no more results)

This bypasses the MaxPageSize policy because each page is within the limit.

### 5.3 Page Size Consideration

| Page Size | Behavior |
|-----------|----------|
| 100 | Multiple round-trips — more overhead but safer for memory |
| 10000 | Fewer round-trips — faster but AD still caps each page to its MaxPageSize (default 1,000) |
| AD MaxPageSize (default 1000) | AD will cap each page to min(requested, MaxPageSize) |

> **Note:** Even though Page Size is set to 10,000, AD will still return at most `MaxPageSize` (default 1,000) entries per page. The effective behavior is multiple pages of 1,000 entries each.

---

## 6. Results

| Metric | Before | After |
|--------|--------|-------|
| LDAP-imported users | capped by AD | All active AD users successfully imported |
| Import New Users search | "No results found" | Successfully discovers new users |

> **Note:** After enabling paged results, the total imported users exceeded initial estimates. This is expected when the AD contains users across multiple OUs, sub-domains, or when disabled account filtering was not previously applied.

---

## 7. Recommendations for Future

| # | Recommendation | Priority | Status |
|---|----------------|----------|--------|
| 1 | Enable **TLS** (Use TLS = Yes or switch to LDAPS port 636) to encrypt LDAP traffic | Medium | Pending |
| 2 | Set up **scheduled LDAP sync** (Automatic Actions) to keep users up-to-date | Medium | Pending |
| 3 | Review imported users to verify no unwanted accounts (service accounts, shared mailboxes) | Low | Pending |
| 4 | Document the LDAP filter in GLPI admin runbook | Low | Done (this PRD + README) |

---

## 8. References

- [Microsoft - LDAP Policies](https://learn.microsoft.com/en-us/windows/win32/ad/ldap-policies)
- [GLPI Documentation - LDAP Directory](https://glpi-install.readthedocs.io/en/latest/authentication/ldap.html)
- [RFC 2696 - Simple Paged Results Control](https://www.rfc-editor.org/rfc/rfc2696)
- [Microsoft - userAccountControl Flags](https://learn.microsoft.com/en-us/troubleshoot/windows-server/active-directory/useraccountcontrol-manipulate-account-properties)
