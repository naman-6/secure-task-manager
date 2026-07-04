// Jenkinsfile
//
// Secure Task & Asset Manager - Cloud-Hybrid DevSecOps Pipeline
// Designed for: GitHub -> Jenkins (Mothership) -> Docker Hub -> ESXi K8s Cluster

pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '20'))
        ansiColor('xterm')
    }

    environment {
        // Points to the Jenkins Credential ID created in Step 1
        DOCKER_HUB_CREDS   = "docker-hub-credentials"
        DOCKER_USER        = "naman96"
        
        // Tagging convention using Jenkins build numbers and truncated git hashes
        IMAGE_TAG          = "${env.BUILD_NUMBER}-${env.GIT_COMMIT?.take(7) ?: 'nogit'}"
        
        // Official Docker Hub image paths
        BACKEND_IMAGE      = "${DOCKER_USER}/secure-task-manager-backend"
        FRONTEND_IMAGE     = "${DOCKER_USER}/secure-task-manager-frontend"
        
        K8S_NAMESPACE      = "taskmanager"
        KUBECONFIG_CRED_ID = "kubeconfig-esxi-cluster"
    }

    parameters {
        booleanParam(name: 'FAIL_ON_CRITICAL_VULN', defaultValue: true,
                     description: 'Abort the pipeline if Trivy finds CRITICAL severity vulnerabilities.')
        booleanParam(name: 'SKIP_DEPLOY', defaultValue: false,
                     description: 'Run all scan/build stages but skip the remote kubectl deployment.')
    }

    stages {

        // ---------------------------------------------------------------
        stage('1. Checkout') {
            steps {
                echo "==> Checking out source code from GitHub"
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
                            python3 -m pip install --user --quiet --break-system-packages semgrep || true
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
                                python3 -m pip install --user --quiet --break-system-packages pip-audit || true
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
        stage('4. Container Build & Push to Docker Hub') {
            steps {
                echo "==> Building backend production container"
                sh "docker build -t ${BACKEND_IMAGE}:${IMAGE_TAG} -t ${BACKEND_IMAGE}:latest ./backend"

                echo "==> Building frontend production container"
                sh "docker build -t ${FRONTEND_IMAGE}:${IMAGE_TAG} -t ${FRONTEND_IMAGE}:latest ./frontend"

                echo "==> Securely authenticating and pushing to Docker Hub"
                withCredentials([usernamePassword(credentialsId: "${DOCKER_HUB_CREDS}", usernameVariable: 'DB_USER', passwordVariable: 'DB_PASS')]) {
                    sh """
                        echo "\$DB_PASS" | docker login -u "\$DB_USER" --password-stdin
                        docker push ${BACKEND_IMAGE}:${IMAGE_TAG}
                        docker push ${BACKEND_IMAGE}:latest
                        docker push ${FRONTEND_IMAGE}:${IMAGE_TAG}
                        docker push ${FRONTEND_IMAGE}:latest
                        docker logout
                    """
                }
            }
        }

        // ---------------------------------------------------------------
        stage('5. Container Scanning (Trivy)') {
            steps {
                echo "==> Scanning built Docker Hub images for vulnerabilities"
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
                            error("Trivy detected CRITICAL image vulnerabilities. Breaking build cascade.")
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
                echo "==> Scanning deployment manifests with Checkov"
                sh '''
                    set -e
                    python3 -m pip install --user --quiet --break-system-packages checkov || true
                    python3 -m checkov -d k8s/ --framework kubernetes --break-system-packages --output json --output-file-path checkov-report.json || true
                    python3 -m checkov -d k8s/ --framework kubernetes --break-system-packages --compact || true
                    echo "Checkov static analysis complete."
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
                echo "==> Authenticating to external ESXi K8s Master via Kubeconfig File"
                withCredentials([file(credentialsId: "${KUBECONFIG_CRED_ID}", variable: 'KUBECONFIG_FILE')]) {
                    sh """
                        export KUBECONFIG=\${KUBECONFIG_FILE}

                        echo "--> Verifying cluster routing integrity"
                        kubectl cluster-info
                        kubectl get nodes -o wide

                        echo "--> Orchestrating structural namespaces and core configurations"
                        kubectl apply -f k8s/configmap.yaml
                        kubectl apply -f k8s/secrets.yaml
                        kubectl apply -f k8s/network-policy.yaml

                        echo "--> Deploying high-availability storage and database tier"
                        kubectl apply -f k8s/postgres-service.yaml
                        kubectl apply -f k8s/postgres-statefulset.yaml

                        # Ensures backend wait_for_db helper syncs properly
                        echo "--> Deploying application tiers"
                        kubectl apply -f k8s/backend-service.yaml
                        kubectl apply -f k8s/backend-deployment.yaml
                        kubectl apply -f k8s/frontend-service.yaml
                        kubectl apply -f k8s/frontend-deployment.yaml

                        echo "--> Pushing fresh application builds straight from Docker Hub"
                        kubectl -n ${K8S_NAMESPACE} set image deployment/backend backend=${BACKEND_IMAGE}:${IMAGE_TAG}
                        kubectl -n ${K8S_NAMESPACE} set image deployment/frontend frontend=${FRONTEND_IMAGE}:${IMAGE_TAG}

                        echo "--> Confirming rollout transition status strings"
                        kubectl -n ${K8S_NAMESPACE} rollout status deployment/backend --timeout=180s
                        kubectl -n ${K8S_NAMESPACE} rollout status deployment/frontend --timeout=180s

                        echo "--> Post-deployment environment mapping"
                        kubectl -n ${K8S_NAMESPACE} get pods -o wide
                        kubectl -n ${K8S_NAMESPACE} get svc
                    """
                }
            }
        }
    }

    post {
        success {
            echo "DevSecOps core lifecycle completed successfully! Build Tag: ${IMAGE_TAG}"
        }
        failure {
            echo "Pipeline halted due to scanning failure. Investigate archived JSON reports."
        }
        always {
            sh 'docker image prune -f || true'
        }
    }
}
