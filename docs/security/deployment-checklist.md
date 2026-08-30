# Pre-Deployment Security Checklist

**Purpose:** the security gate before any release. Work through every item, then sign off in the "Final sign-off" section. Evidence for checked items goes in `docs/security/evidence/`.

> This is a framework — concrete values (domain, server, cert) are filled in when the deployment environment is provisioned. Items with ⏳ are pending deployment.

## 1. Transport security

- [ ] HTTPS is enforced for all traffic (HTTP→HTTPS redirect on the reverse proxy)
- [ ] TLS certificate issued and auto-renewal configured (e.g. Let's Encrypt)
- [ ] HSTS header set
- [ ] IP-direct access does not bypass HTTPS (redirects to the domain)

## 2. Access control

- [ ] Auth model decided and implemented (Nginx basic auth and/or application-level auth) — see threat-model T1/T2
- [ ] Default passwords changed; credentials not shared in chat or repo
- [ ] Database uses a least-privilege app account (not root)

## 3. Secrets

- [ ] No secrets in the repo, images, or frontend build (see secret-handling)
- [ ] `.env` not present on the server in world-readable form (`chmod 600`)
- [ ] Production secrets in AWS Secrets Manager (or equivalent), not hard-coded
- [ ] GitHub Actions secrets set, not written in workflow files

## 4. API / application config

- [ ] `debug = false` / no stack traces in production error responses (threat-model T8)
- [ ] CORS restricted to the actual frontend origin(s)
- [ ] Input length/type validation on all endpoints; error messages sanitized
- [ ] External API calls (Vicmap / CFA / BOM) have timeouts and graceful failure (T7)
- [ ] Request size limits and a basic rate-limit decision in place (T9, T10)

## 5. Security headers / reverse proxy

- [ ] Nginx (or equivalent) config reviewed: headers — Content-Security-Policy, X-Content-Type-Options, X-Frame-Options, Referrer-Policy
- [ ] Reverse proxy config reviewed before it is used in production
- [ ] Security Groups / firewall: only 80/443 (and SSH from admin IP, or SSM only) exposed

## 6. Data

- [ ] No addresses / coordinates / support needs in backend logs (privacy-requirements §3)
- [ ] Database backups configured; deletion protection on RDS (if used)
- [ ] Encryption at rest (RDS/volumes) enabled
- [ ] No real personal data in seed/mock data

## 7. Build / CI

- [ ] Backend CI runs tests and dependency scan
- [ ] Frontend build contains no secrets
- [ ] Dependency scan clean or documented exceptions (see dependency-scan)

## 8. Monitoring (student-project level)

- [ ] Basic access/error logs reachable on the server
- [ ] (Optional) CloudWatch / CloudTrail / GuardDuty enabled for the AWS account

## 9. Final sign-off

- [ ] Every relevant item above checked
- [ ] Evidence archived in `docs/security/evidence/`
- [ ] Signed off by: ____________  Date: ____________
