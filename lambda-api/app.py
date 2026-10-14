"""AWS Lambda CRUD handler for a DynamoDB table whose partition key is ``id``.

Configure the table name with the DYNAMODB_TABLE Lambda environment variable.
Accepts direct Lambda JSON events and API Gateway proxy requests.

Update accepts either format:
  {"operation": "update", "payload": {"Item": {"id": "1234ABCD", "number": 10}}}
  {"operation": "update", "payload": {"Key": {"id": "1234ABCD"},
      "UpdateExpression": "SET #num = :newNum",
      "ExpressionAttributeNames": {"#num": "number"},
      "ExpressionAttributeValues": {":newNum": 10}}}
"""

import json
import os
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError


TABLE_NAME = os.environ.get("DYNAMODB_TABLE")
dynamodb = boto3.resource("dynamodb")

# UpdateItem parameters a request may pass through (Key is handled separately).
UPDATE_ITEM_PARAMETERS = (
	"UpdateExpression",
	"ConditionExpression",
	"ExpressionAttributeNames",
	"ExpressionAttributeValues",
	"ReturnValues",
)


def _json_default(value):
	# DynamoDB returns numbers as Decimal; send them back as JSON numbers.
	if isinstance(value, Decimal):
		return int(value) if value == value.to_integral_value() else float(value)
	return str(value)


def _response(status_code, data):
	return {
		"statusCode": status_code,
		"headers": {"Content-Type": "application/json"},
		"body": json.dumps(data, default=_json_default),
	}


def _parse_request(event):
	if isinstance(event, str):
		event = json.loads(event)
	if not isinstance(event, dict):
		raise ValueError("Request must be a JSON object")

	# API Gateway proxy integrations place the request JSON in event['body'].
	if "body" in event:
		body = event["body"]
		if isinstance(body, str):
			event = json.loads(body)
		elif isinstance(body, dict):
			event = body
		else:
			raise ValueError("Request body must be a JSON object")
	if not isinstance(event, dict):
		raise ValueError("Request must be a JSON object")
	# DynamoDB rejects Python floats; re-parse so decimals such as 10.5 become Decimal.
	return json.loads(json.dumps(event), parse_float=Decimal)


def _get_key(payload):
	key = payload.get("Key")
	if key is None and "id" in payload:
		key = {"id": payload["id"]}
	if not isinstance(key, dict) or "id" not in key:
		raise ValueError('Provide payload.Key or payload.id containing the table key "id"')
	return key


def lambda_handler(event, context):
	try:
		if not TABLE_NAME:
			raise ValueError("Set the DYNAMODB_TABLE environment variable")

		request = _parse_request(event)
		operation = request.get("operation", "").lower()
		payload = request.get("payload") or {}
		if not isinstance(payload, dict):
			raise ValueError("payload must be a JSON object")
		table = dynamodb.Table(TABLE_NAME)

		if operation == "create":
			item = payload.get("Item")
			if not isinstance(item, dict) or "id" not in item:
				raise ValueError('Create requires payload.Item with an "id" attribute')
			table.put_item(Item=item)
			return _response(201, {"message": "Item created", "item": item})

		if operation == "read":
			result = table.get_item(Key=_get_key(payload))
			item = result.get("Item")
			if item is None:
				return _response(404, {"message": "Item not found"})
			return _response(200, {"item": item})

		if operation == "update" and "UpdateExpression" in payload:
			# Native UpdateItem format: Key + UpdateExpression (+ names/values).
			params = {
				name: payload[name]
				for name in UPDATE_ITEM_PARAMETERS
				if name in payload
			}
			params.setdefault("ReturnValues", "ALL_NEW")
			result = table.update_item(Key=_get_key(payload), **params)
			return _response(200, {"message": "Item updated", "item": result.get("Attributes")})

		if operation == "update":
			# Simple format: Item with id plus the attributes to set.
			item = payload.get("Item")
			if not isinstance(item, dict) or "id" not in item:
				raise ValueError(
					'Update requires payload.Item with an "id" attribute, '
					"or payload.Key with payload.UpdateExpression"
				)
			attributes = {name: value for name, value in item.items() if name != "id"}
			if not attributes:
				raise ValueError("Update requires at least one attribute besides id")
			names = {f"#n{i}": name for i, name in enumerate(attributes)}
			values = {f":v{i}": value for i, value in enumerate(attributes.values())}
			expression = "SET " + ", ".join(
				f"#n{i} = :v{i}" for i in range(len(attributes))
			)
			result = table.update_item(
				Key={"id": item["id"]},
				UpdateExpression=expression,
				ExpressionAttributeNames=names,
				ExpressionAttributeValues=values,
				ReturnValues="ALL_NEW",
			)
			return _response(200, {"message": "Item updated", "item": result["Attributes"]})

		if operation == "delete":
			result = table.delete_item(Key=_get_key(payload), ReturnValues="ALL_OLD")
			item = result.get("Attributes")
			if item is None:
				return _response(404, {"message": "Item not found"})
			return _response(200, {"message": "Item deleted", "item": item})

		raise ValueError('operation must be "create", "read", "update", or "delete"')

	except (ValueError, KeyError, json.JSONDecodeError) as error:
		return _response(400, {"error": str(error)})
	except ClientError as error:
		details = error.response.get("Error", {})
		message = details.get("Message", "DynamoDB error")
		# Bad expressions or a failed ConditionExpression are client errors.
		if details.get("Code") in ("ValidationException", "ConditionalCheckFailedException"):
			return _response(400, {"error": message})
		return _response(500, {"error": message})
