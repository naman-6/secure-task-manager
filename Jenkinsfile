// Jenkinsfile
//
// Secure Task & Asset Manager - CI/CD Pipeline
//
// Designed to run entirely on the "devsecops-mothership" VM using a Jenkins
// agent with Docker, Python 3, Node.js, and kubectl installed locally.
// This VM also hosts the local, insecure Docker registry at localhost:5000
// which the built images are pushed to before being deployed to the
// external, on-prem ESXi Kubernetes cluster (1 master, 2 workers).
//
// PREREQUISITES ON THE MOTHERSHIP VM / JENKINS AGENT:
//   - Docker Engine with a registry container running:
//       docker run -d -p 5000:5000 --restart=always --name registry registry:2
//   - Python 3.11+, pip, bandit, semgrep, pip-audit installed on PATH
//       (or available via the "python3 -m pip install --user ..." fallback
//       used below).
//   - Node.js 20+ and npm on PATH.
//   - trivy CLI installed (https://aquasecurity.github.io/trivy/).
//   - checkov CLI installed (pip install checkov).
//   - kubectl installed and configured with a kubeconfig (via Jenkins
//     credential "kubeconfig-esxi-cluster") that can reach the external
//     ESXi master node's API server.
//   - Jenkins credential "kubeconfig-esxi-cluster" (Secret file) containing
//     the kubeconfig for the remote cluster.

pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '20'))
        ansiColor('xterm')
    }

    environment {
        REGISTRY            = "localhost:5000"
        IMAGE_TAG           = "${env.BUILD_NUMBER}-${env.GIT_COMMIT?.take(7) ?: 'nogit'}"
        BACKEND_IMAGE       = "${REGISTRY}/taskmanager-backend"
        FRONTEND_IMAGE      = "${REGISTRY}/taskmanager-frontend"
        K8S_NAMESPACE       = "taskmanager"
        KUBECONFIG_CRED_ID  = "kubeconfig-esxi-cluster"
        // Address of the mothership registry AS SEEN BY the ESXi worker
        // nodes (not "localhost", since the workers are separate hosts).
        // Override this at the Jenkins job level or via a parameter.
        MOTHERSHIP_REGISTRY_EXTERNAL = "${params.MOTHERSHIP_IP ?: '192.168.1.10'}:5000"
    }

    parameters {
        string(name: 'MOTHERSHIP_IP', defaultValue: '192.168.1.10',
               description: 'IP/hostname of this mothership VM as reachable from the ESXi worker nodes.')
        booleanParam(name: 'FAIL_ON_CRITICAL_VULN', defaultValue: true,
               description: 'Abort the pipeline if Trivy finds CRITICAL severity vulnerabilities.')
        booleanParam(name: 'SKIP_DEPLOY', defaultValue: false,
               description: 'Run all scan/build stages but skip the remote kubectl deployment.')
    }

    stages {

        // ---------------------------------------------------------------
        stage('1. Checkout') {
            steps {
                echo "==> Checking out source code"
                checkout scm
                sh 'git log -1 --pretty=format:"Commit: %H | Author: %an | Message: %s"'
            }
        }

        // ---------------------------------------------------------------
        stage('2. SAST Scanning') {
            parallel {
                stage('Bandit (Python)') {
                    steps {
                        echo "==> Running Bandit against backend/"
                        sh '''
                            set -e
                            python3 -m pip install --user --quiet bandit || true
                            python3 -m bandit -r backend/ -f json -o bandit-report.json -ll || BANDIT_EXIT=$?
                            python3 -m bandit -r backend/ -f screen || true
                            echo "Bandit scan complete. Report: bandit-report.json"
                        '''
                    }
                    post {
                        always {
                            archiveArtifacts artifacts: 'bandit-report.json', allowEmptyArchive: true
                        }
                    }
                }
                stage('Semgrep (Repo-wide)') {
                    steps {
                        echo "==> Running Semgrep against the entire repository"
                        sh '''
                            set -e
                            python3 -m pip install --user --quiet semgrep || true
                            python3 -m semgrep scan --config auto --json --output semgrep-report.json . || true
                            python3 -m semgrep scan --config auto . || true
                            echo "Semgrep scan complete. Report: semgrep-report.json"
                        '''
                    }
                    post {
                        always {
                            archiveArtifacts artifacts: 'semgrep-report.json', allowEmptyArchive: true
                        }
                    }
                }
            }
        }

        // ---------------------------------------------------------------
        stage('3. SCA Scanning') {
            parallel {
                stage('pip-audit (Backend deps)') {
                    steps {
                        echo "==> Auditing Python dependencies with pip-audit"
                        dir('backend') {
                            sh '''
                                set -e
                                python3 -m pip install --user --quiet pip-audit || true
                                python3 -m pip_audit -r requirements.txt -f json -o ../pip-audit-report.json || true
                                python3 -m pip_audit -r requirements.txt || true
                                echo "pip-audit scan complete."
                            '''
                        }
                    }
                    post {
                        always {
                            archiveArtifacts artifacts: 'pip-audit-report.json', allowEmptyArchive: true
                        }
                    }
                }
                stage('npm audit (Frontend deps)') {
                    steps {
                        echo "==> Auditing Node dependencies with npm audit"
                        dir('frontend') {
                            sh '''
                                set -e
                                npm install --no-audit --no-fund --package-lock-only || true
                                npm audit --json > ../npm-audit-report.json || true
                                npm audit || true
                                echo "npm audit scan complete."
                            '''
                        }
                    }
                    post {
                        always {
                            archiveArtifacts artifacts: 'npm-audit-report.json', allowEmptyArchive: true
                        }
                    }
                }
            }
        }

        // ---------------------------------------------------------------
        stage('4. Container Build & Push to Local Registry') {
            steps {
                echo "==> Building backend image: ${BACKEND_IMAGE}:${IMAGE_TAG}"
                sh """
                    docker build -t ${BACKEND_IMAGE}:${IMAGE_TAG} -t ${BACKEND_IMAGE}:latest ./backend
                """

                echo "==> Building frontend image: ${FRONTEND_IMAGE}:${IMAGE_TAG}"
                sh """
                    docker build -t ${FRONTEND_IMAGE}:${IMAGE_TAG} -t ${FRONTEND_IMAGE}:latest ./frontend
                """

                echo "==> Pushing images to mothership local registry (${REGISTRY})"
                sh """
                    docker push ${BACKEND_IMAGE}:${IMAGE_TAG}
                    docker push ${BACKEND_IMAGE}:latest
                    docker push ${FRONTEND_IMAGE}:${IMAGE_TAG}
                    docker push ${FRONTEND_IMAGE}:latest
                """
            }
        }

        // ---------------------------------------------------------------
        stage('5. Container Scanning (Trivy)') {
            steps {
                echo "==> Scanning built images for OS/library vulnerabilities with Trivy"
                script {
                    def trivyExitCode = 0
                    sh """
                        trivy image --format json --output trivy-backend-report.json ${BACKEND_IMAGE}:${IMAGE_TAG} || true
                        trivy image --format table ${BACKEND_IMAGE}:${IMAGE_TAG} || true
                        trivy image --format json --output trivy-frontend-report.json ${FRONTEND_IMAGE}:${IMAGE_TAG} || true
                        trivy image --format table ${FRONTEND_IMAGE}:${IMAGE_TAG} || true
                    """
                    if (params.FAIL_ON_CRITICAL_VULN) {
                        trivyExitCode = sh(
                            script: """
                                trivy image --exit-code 1 --severity CRITICAL --ignore-unfixed ${BACKEND_IMAGE}:${IMAGE_TAG}
                                trivy image --exit-code 1 --severity CRITICAL --ignore-unfixed ${FRONTEND_IMAGE}:${IMAGE_TAG}
                            """,
                            returnStatus: true
                        )
                        if (trivyExitCode != 0) {
                            error("Trivy detected CRITICAL vulnerabilities. Failing pipeline (FAIL_ON_CRITICAL_VULN=true).")
                        }
                    }
                }
            }
            post {
                always {
                    archiveArtifacts artifacts: 'trivy-*-report.json', allowEmptyArchive: true
                }
            }
        }

        // ---------------------------------------------------------------
        stage('6. Kubernetes Manifest Scanning (Checkov)') {
            steps {
                echo "==> Scanning k8s/ manifests with Checkov"
                sh '''
                    set -e
                    python3 -m pip install --user --quiet checkov || true
                    python3 -m checkov -d k8s/ --framework kubernetes --output json --output-file-path checkov-report.json || true
                    python3 -m checkov -d k8s/ --framework kubernetes --compact || true
                    echo "Checkov scan complete. Report: checkov-report.json"
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'checkov-report.json', allowEmptyArchive: true
                }
            }
        }

        // ---------------------------------------------------------------
        stage('7. Remote Deployment to ESXi K8s Cluster') {
            when {
                expression { return !params.SKIP_DEPLOY }
            }
            steps {
                echo "==> Deploying to the on-prem ESXi Kubernetes cluster (external master node)"
                withCredentials([file(credentialsId: "${KUBECONFIG_CRED_ID}", variable: 'KUBECONFIG_FILE')]) {
                    sh """
                        export KUBECONFIG=\${KUBECONFIG_FILE}

                        echo "--> Verifying connectivity to the remote cluster"
                        kubectl cluster-info
                        kubectl get nodes -o wide

                        echo "--> Applying namespace, config, and secrets first"
                        kubectl apply -f k8s/configmap.yaml
                        kubectl apply -f k8s/secrets.yaml

                        echo "--> Applying database tier"
                        kubectl apply -f k8s/postgres-service.yaml
                        kubectl apply -f k8s/postgres-statefulset.yaml

                        echo "--> Applying network policies"
                        kubectl apply -f k8s/network-policy.yaml

                        echo "--> Applying backend tier"
                        kubectl apply -f k8s/backend-service.yaml
                        kubectl apply -f k8s/backend-deployment.yaml

                        echo "--> Applying frontend tier"
                        kubectl apply -f k8s/frontend-service.yaml
                        kubectl apply -f k8s/frontend-deployment.yaml

                        echo "--> Setting freshly built image tags on the Deployments"
                        kubectl -n ${K8S_NAMESPACE} set image deployment/backend \
                            backend=${MOTHERSHIP_REGISTRY_EXTERNAL}/taskmanager-backend:${IMAGE_TAG}
                        kubectl -n ${K8S_NAMESPACE} set image deployment/frontend \
                            frontend=${MOTHERSHIP_REGISTRY_EXTERNAL}/taskmanager-frontend:${IMAGE_TAG}

                        echo "--> Waiting for rollouts to complete"
                        kubectl -n ${K8S_NAMESPACE} rollout status deployment/backend --timeout=180s
                        kubectl -n ${K8S_NAMESPACE} rollout status deployment/frontend --timeout=180s

                        echo "--> Post-deploy status"
                        kubectl -n ${K8S_NAMESPACE} get pods -o wide
                        kubectl -n ${K8S_NAMESPACE} get svc
                    """
                }
            }
        }
    }

    post {
        success {
            echo "Pipeline completed successfully. Build tag: ${IMAGE_TAG}"
        }
        failure {
            echo "Pipeline FAILED. Check the archived SAST/SCA/Trivy/Checkov reports for details."
        }
        always {
            sh 'docker image prune -f || true'
        }
    }
}
