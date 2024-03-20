# If not already forked, fork the remote repository (https://github.com/aws-solutions-library-samples/guidance-for-secure-access-to-external-package-repositories-on-aws.git) and change working directory to shell folder
# cd guidance-for-secure-access-to-external-package-repositories-on-aws/shell/
# chmod u+x create-github-stack.sh
# source ./create-github-stack.sh

export PRIVATE_GITHUB_TOKEN_SECRET_NAME=$(aws secretsmanager create-secret --name $STACK_NAME-git-pat --secret-string $PRIVATE_GITHUB_PAT --query Name --output text)
export PRIVATE_GITHUB_EMAIL_SECRET_NAME=$(aws secretsmanager create-secret --name $STACK_NAME-git-email --secret-string $PRIVATE_GITHUB_EMAIL  --query Name --output text)
export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export S3_ARTIFACTS_BUCKET_NAME=${STACK_NAME}-${ACCOUNT_ID}-github

aws s3 mb s3://${S3_ARTIFACTS_BUCKET_NAME} --region us-east-1

aws cloudformation create-stack \
--stack-name ${STACK_NAME} \
--template-body file://../cfn/github-private-repo.yaml \
--parameters \
ParameterKey=S3ArtifactsBucket,ParameterValue=${S3_ARTIFACTS_BUCKET_NAME} \
ParameterKey=CodePipelineName,ParameterValue=${CODEPIPELINE_NAME} \
ParameterKey=SNSEmail,ParameterValue=${SNS_EMAIL} \
ParameterKey=PrivateGitHubBranch,ParameterValue=${PRIVATE_GITHUB_BRANCH} \
ParameterKey=PrivateGitHubOwner,ParameterValue=${PRIVATE_GITHUB_OWNER} \
ParameterKey=PrivateGitHubRepo,ParameterValue=${PRIVATE_GITHUB_REPO} \
ParameterKey=PrivateGitHubToken,ParameterValue=${PRIVATE_GITHUB_TOKEN_SECRET_NAME} \
ParameterKey=PrivateGitHubUsername,ParameterValue=${PRIVATE_GITHUB_USERNAME} \
ParameterKey=PrivateGitHubEmail,ParameterValue=${PRIVATE_GITHUB_EMAIL_SECRET_NAME} \
ParameterKey=CodeServicesVpc,ParameterValue=${CODESERVICES_VPC_ID} \
ParameterKey=CodeServicesSubnet,ParameterValue=${CODESERVICES_SUBNET_ID1}\\,${CODESERVICES_SUBNET_ID2} \
--capabilities CAPABILITY_IAM

aws cloudformation describe-stacks --stack-name $STACK_NAME --query "Stacks[0].StackStatus"
aws cloudformation wait stack-create-complete --stack-name $STACK_NAME
aws cloudformation describe-stacks --stack-name $STACK_NAME --query "Stacks[0].StackStatus"