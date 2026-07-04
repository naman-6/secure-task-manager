# Secure Task & Asset Manager

A production-ready, 3-tier web application (React/Vite → FastAPI → PostgreSQL)
built for deployment to an **on-premise, bare-metal Kubernetes cluster**
(1 master + 2 workers running on ESXi), with CI/CD orchestrated from a
separate **devsecops-mothership** VM.

---

## 1. System Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                     DEVSECOPS-MOTHERSHIP VM                              │
│                                                                            │
│   ┌──────────────┐    ┌────────────────────────────────────────────┐    │
│   │   Developer  │───▶│                 Jenkins                     │    │
│   │  git push    │    │  1. Checkout                                │    │
│   └──────────────┘    │  2. SAST   (Bandit + Semgrep)                │    │
│                        │  3. SCA    (pip-audit + npm audit)          │    │
│                        │  4. Build  (docker build)                   │    │
│                        │  5. Scan   (Trivy - container images)       │    │
│                        │  6. Scan   (Checkov - k8s manifests)        │    │
│                        │  7. Deploy (kubectl → remote cluster)       │    │
│                        └────────────────┬─────────────────────────┬─┘    │
│                                          │                         │      │
│                        ┌─────────────────▼───────────────┐        │      │
│                        │  Local Docker Registry            │        │      │
│                        │  localhost:5000                    │        │      │
│                        │  - taskmanager-backend:<tag>        │        │      │
│                        │  - taskmanager-frontend:<tag>       │        │      │
│                        └─────────────────┬───────────────┘        │      │
│                                          │  docker push / pull      │      │
└──────────────────────────────────────────┼──────────────────────────┼──────┘
                                            │ (network reachable:      │
                                            │  <mothership-ip>:5000)   │ kubectl apply
                                            │                          │ (kubeconfig)
                                            ▼                          ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                  ON-PREM BARE-METAL KUBERNETES CLUSTER (ESXi)            │
│                                                                            │
│   ┌───────────────────────┐        ┌────────────────────────────────┐   │
│   │   k8s-master (ESXi VM) │       │   k8s-worker-1 (ESXi VM)         │   │
│   │   - kube-apiserver     │       │   - kubelet, kube-proxy          │   │
│   │   - etcd, scheduler    │       │   - CNI (Calico/Cilium)          │   │
│   └───────────────────────┘        │   - Pods: frontend / backend      │   │
│                                     │   - NodePort :30080 exposed       │   │
│                                     └────────────────────────────────┘   │
│                                                                            │
│                                     ┌────────────────────────────────┐   │
│                                     │   k8s-worker-2 (ESXi VM)         │   │
│                                     │   - kubelet, kube-proxy          │   │
│                                     │   - CNI (Calico/Cilium)          │   │
│                                     │   - Pods: frontend / backend /   │   │
│                                     │     postgres (StatefulSet)        │   │
│                                     │   - NodePort :30080 exposed       │   │
│                                     └────────────────────────────────┘   │
│                                                                            │
│   Namespace: taskmanager                                                 │
│   ┌────────────────┐   ┌───────────────┐   ┌──────────────────────┐     │
│   │ frontend-service│──▶│backend-service│──▶│  postgres-service      │     │
│   │  (NodePort:30080)│   │  (ClusterIP)  │   │  (Headless, StatefulSet)│     │
│   └────────────────┘   └───────────────┘   └──────────────────────┘     │
│         ▲                                                                 │
│         │ NetworkPolicy: default-deny + explicit tier-to-tier allow-lists │
└─────────┼──────────────────────────────────────────────────────────────┘
          │
          │  http://<worker-1-ip>:30080  or  http://<worker-2-ip>:30080
          ▼
     End Users / Browsers
```

**Traffic flow summary:**
1. A developer pushes code to the Git repository monitored by Jenkins on the mothership VM.
2. Jenkins runs SAST/SCA scans, builds both Docker images, pushes them to the mothership's local registry (`localhost:5000`), scans the images with Trivy and the Kubernetes manifests with Checkov.
3. Jenkins then uses `kubectl` (via a stored kubeconfig) to apply manifests and update Deployments on the **external** ESXi Kubernetes cluster, referencing images by the mothership's **network-reachable** address (`<mothership-ip>:5000/...`), not `localhost`.
4. Worker nodes pull the images from the mothership registry and schedule the `frontend`, `backend`, and `postgres` pods.
5. End users hit any worker node's IP on **NodePort 30080** to reach the React frontend, which reverse-proxies API calls to the backend Service internally.

---

## 2. Repository Structure

```
├── frontend/                  # React (Vite) SPA
│   ├── Dockerfile              # multi-stage, non-root nginx-unprivileged runtime
│   ├── nginx.conf
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── api.js
│       ├── index.css
│       └── components/
│           ├── TaskForm.jsx
│           ├── TaskTable.jsx
│           ├── StatusPill.jsx
│           └── Toolbar.jsx
├── backend/                   # FastAPI REST API
│   ├── Dockerfile              # multi-stage, non-root runtime
│   ├── requirements.txt
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   └── schemas.py
├── k8s/                        # Kubernetes manifests
│   ├── configmap.yaml           # includes Namespace definition
│   ├── secrets.yaml
│   ├── postgres-statefulset.yaml
│   ├── postgres-service.yaml
│   ├── backend-deployment.yaml
│   ├── backend-service.yaml
│   ├── frontend-deployment.yaml
│   ├── frontend-service.yaml     # NodePort :30080
│   └── network-policy.yaml
├── Jenkinsfile                 # 7-stage DevSecOps pipeline
├── docker-compose.yml          # local dev stack for the mothership VM
└── README.md
```

---

## 3. Security & Bare-Metal Design Decisions

| Requirement | Implementation |
|---|---|
| No build tools in final images | Multi-stage Dockerfiles for both frontend (`node:20-alpine` builder → `nginx-unprivileged` runtime) and backend (`python:3.12-slim` builder producing wheels → slim runtime with no compiler) |
| Non-root containers | Backend runs as UID `10001` (`appuser`); Frontend runs as UID `101` (built into `nginxinc/nginx-unprivileged`) |
| `readOnlyRootFilesystem: true` | Set on both Deployments; writable paths (`/tmp`, nginx cache/run dirs, backend `/app/tmp`) are mounted as `emptyDir` volumes |
| `allowPrivilegeEscalation: false` | Set on all application containers |
| `runAsNonRoot: true` | Set at both pod and container `securityContext` level |
| No cloud LoadBalancer | `frontend-service.yaml` uses `type: NodePort` with a fixed `nodePort: 30080`, reachable on **any** cluster node's IP |
| Network segmentation | `network-policy.yaml` implements default-deny-all plus explicit allow rules: Postgres ⟵ Backend only; Backend ⟵ Frontend only; Frontend ⟵ any (NodePort ingress) |
| Secrets not hard-coded | DB credentials sourced from a Kubernetes `Secret` (`secrets.yaml`) injected as env vars — see the in-file warning about replacing base64 with Sealed Secrets/Vault for real production use |
| Structured logging | Backend emits single-line JSON logs (timestamp, level, correlation ID, method, path, status, duration) to stdout for aggregation |
| Health checks | Backend: `/healthz` (liveness) and `/ready` (readiness, checks DB connectivity). Frontend: `/healthz` served directly by Nginx |

---

## 4. Running Locally on the Mothership VM (Docker Compose)

This is the fastest inner-loop for development/testing before anything goes
through the Jenkins pipeline.

### Prerequisites
- Docker Engine + Docker Compose plugin installed on the mothership VM.
- Ports `5432`, `8000`, and `8081` free on the host.

### Steps

```bash
# From the repository root
cd secure-task-manager

# Build and start all three tiers
docker compose up --build -d

# Watch logs (optional)
docker compose logs -f backend

# Check container health
docker compose ps
```

### Accessing the app locally
- **Frontend (UI):** http://localhost:8081
- **Backend API docs (Swagger):** http://localhost:8000/docs
- **Backend health:** http://localhost:8000/healthz
- **Backend readiness:** http://localhost:8000/ready
- **Postgres:** `localhost:5432` (user `taskadmin`, db `taskmanager` — see `docker-compose.yml` for the local-only password)

### Tearing down

```bash
docker compose down          # stop containers, keep the postgres-data volume
docker compose down -v       # stop containers AND delete all local data
```

> **Note:** The frontend's Nginx container proxies `/api/*` requests to a
> host named `backend-service` (see `nginx.conf`). In `docker-compose.yml`,
> the `backend` service is given the network alias `backend-service` so the
> **exact same Nginx config and frontend image** work unmodified in both
> Docker Compose and Kubernetes — only the DNS resolution mechanism differs.

---

## 5. Deploying to the On-Prem ESXi Kubernetes Cluster

### 5.1 One-time cluster prerequisites

1. **CNI with NetworkPolicy support.** Flannel alone does *not* enforce
   `NetworkPolicy` objects — install Calico, Cilium, or Weave Net.
2. **Insecure registry trust.** Since the mothership's registry
   (`<mothership-ip>:5000`) is not TLS-secured by default, configure each
   worker node's container runtime to trust it. For containerd, add to
   `/etc/containerd/config.toml` on every node:
   ```toml
   [plugins."io.containerd.grpc.v1.cri".registry.mirrors."<mothership-ip>:5000"]
     endpoint = ["http://<mothership-ip>:5000"]
   ```
   Then `systemctl restart containerd` on each node.
3. **StorageClass for Postgres.** `postgres-statefulset.yaml` requests a
   `PersistentVolumeClaim`. Ensure a default `StorageClass` exists (e.g.
   `local-path-provisioner` or Longhorn) or set `storageClassName`
   explicitly in that manifest.
4. Update the placeholder `<MOTHERSHIP_IP>` in `k8s/backend-deployment.yaml`
   and `k8s/frontend-deployment.yaml` (or let the Jenkinsfile's
   `kubectl set image` step overwrite it automatically per build).

### 5.2 Manual deployment (without Jenkins)

```bash
export KUBECONFIG=/path/to/esxi-cluster-kubeconfig

kubectl apply -f k8s/configmap.yaml        # creates the "taskmanager" Namespace too
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/postgres-service.yaml
kubectl apply -f k8s/postgres-statefulset.yaml
kubectl apply -f k8s/network-policy.yaml
kubectl apply -f k8s/backend-service.yaml
kubectl apply -f k8s/backend-deployment.yaml
kubectl apply -f k8s/frontend-service.yaml
kubectl apply -f k8s/frontend-deployment.yaml

# Verify rollout
kubectl -n taskmanager rollout status deployment/backend
kubectl -n taskmanager rollout status deployment/frontend
kubectl -n taskmanager get pods -o wide
kubectl -n taskmanager get svc
```

### 5.3 Automated deployment (Jenkins on the mothership)

Configure a Jenkins pipeline job pointing at this repository's `Jenkinsfile`.
Required Jenkins credentials/config:

- **Secret file credential** `kubeconfig-esxi-cluster` — kubeconfig granting
  access to the ESXi cluster's API server (usually reachable at the master
  node's IP on port `6443`).
- **Build parameter** `MOTHERSHIP_IP` — the mothership's IP/hostname as seen
  from the ESXi worker nodes (used to tag images with a pull-able registry
  address instead of `localhost`).

The pipeline runs: Checkout → SAST (Bandit + Semgrep) → SCA (pip-audit +
npm audit) → Build & Push (to `localhost:5000` on the mothership) →
Container scan (Trivy) → Manifest scan (Checkov) → Remote deploy (`kubectl`
against the external cluster).

### 5.4 Accessing the deployed application via NodePort

`frontend-service.yaml` exposes the app on **NodePort `30080`** across
**every node** in the cluster — master and both ESXi workers alike (standard
Kubernetes NodePort behavior routes traffic to the right pod even if it
lands on a node not currently running the frontend pod).

```text
http://<esxi-worker-1-ip>:30080
http://<esxi-worker-2-ip>:30080
http://<esxi-master-ip>:30080     # also works, K8s routes NodePort cluster-wide
```

Find your worker node IPs with:
```bash
kubectl get nodes -o wide
```

To verify the backend independently (from inside the cluster or via
`kubectl port-forward`):
```bash
kubectl -n taskmanager port-forward svc/backend-service 8000:8000
curl http://localhost:8000/healthz
curl http://localhost:8000/ready
```

---

## 6. API Reference (Backend)

| Method | Path | Description |
|---|---|---|
| GET | `/healthz` | Liveness probe |
| GET | `/ready` | Readiness probe (checks DB connectivity) |
| GET | `/api/v1/tasks` | List tasks (supports `status`, `priority`, `search`, `skip`, `limit` query params) |
| POST | `/api/v1/tasks` | Create a task |
| GET | `/api/v1/tasks/{task_id}` | Retrieve a single task |
| PUT | `/api/v1/tasks/{task_id}` | Update a task (partial updates supported) |
| DELETE | `/api/v1/tasks/{task_id}` | Delete a task |

Interactive Swagger docs are available at `/docs` (and ReDoc at `/redoc`)
when running the backend directly (e.g. via `docker compose`).

---

## 7. Troubleshooting

- **Pods stuck in `ImagePullBackOff`:** Verify the worker nodes trust the
  mothership's insecure registry (see 5.1.2) and that `<MOTHERSHIP_IP>` in
  the Deployment manifests is reachable from the worker nodes (not
  `localhost`, which only resolves on the mothership itself).
- **Backend `CrashLoopBackOff` on first deploy:** The backend's `wait_for_db()`
  startup logic retries for up to ~60 seconds; if Postgres takes longer to
  initialize (e.g. slow storage), check `kubectl -n taskmanager logs sts/postgres`.
- **NetworkPolicy blocks legitimate traffic:** Confirm your CNI plugin
  actually enforces `NetworkPolicy` (`kubectl get pods -n kube-system` to
  check for Calico/Cilium components). Flannel-only clusters silently
  ignore these policies.
- **Frontend loads but API calls fail (CORS/404):** Confirm `nginx.conf`'s
  `proxy_pass` target (`backend-service`) matches the actual Kubernetes
  Service name in `backend-service.yaml`.
