# cd guidance-for-secure-access-to-external-package-repositories-on-aws/shell/
# chmod u+x delete-github-stack.sh
# ./delete-github-stack.sh

echo "Emptying and Deleting S3 Bucket: $S3_ARTIFACTS_BUCKET_NAME"
aws s3 rm s3://$S3_ARTIFACTS_BUCKET_NAME --region $AWS_REGION --recursive
aws s3 rb s3://$S3_ARTIFACTS_BUCKET_NAME --region $AWS_REGION

SECURITY_GROUP_ID=$(aws cloudformation describe-stack-resources --stack-name $STACK_NAME --logical-resource-id CodeBuildSecurityGroup --region $AWS_REGION --query "StackResources[0].PhysicalResourceId" --output text)
echo "Deleting Security Group ID: $SECURITY_GROUP_ID"
aws ec2 delete-security-group --group-id $SECURITY_GROUP_ID --region $AWS_REGION

echo "Deleting CloudFormation Stack: $STACK_NAME"
aws cloudformation delete-stack --stack-name $STACK_NAME --region $AWS_REGION
aws cloudformation wait stack-delete-complete --stack-name $STACK_NAME --region $AWS_REGION
echo "DELETE_COMPLETE"

echo "Deleting Secrets Manager Secret: $PRIVATE_GITHUB_TOKEN_SECRET_NAME"
echo "Deleting Secrets Manager Secret: $PRIVATE_GITHUB_EMAIL_SECRET_NAME"
aws secretsmanager delete-secret --secret-id $PRIVATE_GITHUB_TOKEN_SECRET_NAME --region $AWS_REGION
aws secretsmanager delete-secret --secret-id $PRIVATE_GITHUB_EMAIL_SECRET_NAME --region $AWS_REGION