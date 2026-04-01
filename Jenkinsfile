pipeline {
    agent any

    parameters {
        string(name: 'BUILD_TAG', defaultValue: 'v1.0.0', description: 'Version Tag (e.g., v1.0.0)')
    }

    environment {
        // --- CẤU HÌNH DOCKER ---
        DOCKER_REGISTRY_USER = "gk123a"
        IMAGE_NAME = "ai"
        DOCKER_CREDENTIALS_ID = "docker-hub-credentials"
       
        // --- CẤU HÌNH GIT ---
        GIT_REPO_URL = "https://github.com/gk12355a/AI-Meeting-Management.git"
        GIT_CREDENTIALS_ID = "github-https-cred-ids" 
        
        // --- CẤU HÌNH MÔI TRƯỜNG ---
        BRANCH = "${env.GIT_BRANCH}".replaceFirst(/^origin\//, '')
        NAMESPACE = "${BRANCH == 'k8s' ? 'prod' : 'dev'}"
        
        // --- ĐƯỜNG DẪN ---
        PROJECT_ROOT = "." 
        YAML_DIR = "manifest"    
    }

    stages {
        stage('Approval') {
            steps {
                script {
                    input message: "Deploy ${IMAGE_NAME} ${params.BUILD_TAG} to [${NAMESPACE}]?", ok: "Yes, Deploy"
                }
            }
        }

        stage('Checkout Code') {
            steps {
                git branch: "${BRANCH}", 
                    credentialsId: "${GIT_CREDENTIALS_ID}", 
                    url: "${GIT_REPO_URL}"
            }
        }

        stage('Build & Push Docker Image') {
            steps {
                script {
                    dir("${PROJECT_ROOT}") {
                        docker.withRegistry('', "${DOCKER_CREDENTIALS_ID}") {
                            def fullImageName = "${DOCKER_REGISTRY_USER}/${IMAGE_NAME}:${params.BUILD_TAG}-${NAMESPACE}"
                            
                            echo "Building Docker Image..."
                            def image = docker.build(fullImageName, "-f Dockerfile .")
                            
                            echo "Pushing image to Docker Hub..."
                            image.push()
                            image.push("latest") 
                        }
                    }
                }
            }
        }

        stage('GitOps: Update Manifest') {
            steps {
                script {
                    sh "chmod +x update_images_scripts.sh"
                    sh "./update_images_scripts.sh ${IMAGE_NAME} ${params.BUILD_TAG} ${NAMESPACE} ${YAML_DIR}"
                }
            }
        }

        stage('GitOps: Commit & Push') {
            environment {
                NEW_TAG = "${params.BUILD_TAG}"
                CLEAN_URL = "${GIT_REPO_URL.replace("https://", "")}"
            }
            steps {
                withCredentials([
                    usernamePassword(
                        credentialsId: "${GIT_CREDENTIALS_ID}", 
                        usernameVariable: 'GIT_USER', 
                        passwordVariable: 'GIT_PASS'
                    )
                ]) {
                    sh '''
                        set -e
                        git config user.name "jenkins-bot"
                        git config user.email "jenkins@ci.com"

                        git add $YAML_DIR/*.yaml

                        if ! git diff --cached --quiet; then
                            git commit -m "GitOps: Update $IMAGE_NAME image to $NEW_TAG [ci skip]"
                            git pull origin $BRANCH --rebase
                            git push https://$GIT_USER:$GIT_PASS@$CLEAN_URL $BRANCH
                        else
                            echo "No changes in manifest to commit."
                        fi
                    '''
                }
            }
        }
    }
}
