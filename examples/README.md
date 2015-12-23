# Package example Lambda code and upload to S3

```
S3_BUCKET_NAME=example-s3bucket-us-west-2
dir="`mktemp --directory`"
pip install cfnlambda --no-deps -t "$dir"
cp -v example.py "$dir"
zip --junk-paths $dir/example.zip "$dir/example.py" "$dir/cfnlambda.py"
aws --region us-west-2 s3 cp "$dir/example.zip" s3://${S3_BUCKET_NAME}/
rm -rf "$dir"
```

# Deploy CloudFormation template

```
S3_BUCKET_NAME=example-s3bucket-us-west-2
aws --region us-west-2 cloudformation create-stack --stack-name ExampleStack --template-body file://example.json --capabilities "CAPABILITY_IAM" --parameters ParameterKey=S3BucketName,ParameterValue=${S3_BUCKET_NAME}
```

# Look at the outputs

```
aws --region us-west-2 cloudformation describe-stacks --stack-name ExampleStack
```

# Look at the logs

```
LOG_GROUP="`aws --region us-west-2 cloudformation describe-stack-resources --stack-name ExampleStack --logical-resource-id ExecuteSum --output text | awk '{print $3}'`"
LOG_STREAM="`aws --region us-west-2 cloudformation describe-stack-resources --stack-name ExampleStack --logical-resource-id SumInfo --output text | awk '{print $3}'`"
aws --region us-west-2 logs get-log-events --log-group-name /aws/lambda/$LOG_GROUP --log-stream-name $LOG_STREAM --output text
```

# Delete CloudFormation stack

```
aws --region us-west-2 cloudformation delete-stack --stack-name ExampleStack
```
