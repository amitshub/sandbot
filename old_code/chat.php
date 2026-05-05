$message = $body;

// Get last few messages (optional)
$history = []; // you can fetch from DB

$payload = json_encode([
    "message" => $message,
    "history" => $history
]);

$ch = curl_init("http://localhost:8000/ai-reply");
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_POSTFIELDS, $payload);
curl_setopt($ch, CURLOPT_HTTPHEADER, [
    'Content-Type: application/json'
]);

$response = curl_exec($ch);
curl_close($ch);

$result = json_decode($response, true);

$ai_reply = $result['reply'] ?? "Thanks for your message.";

// Now send via Twilio
$twilio = new Client(self::TWILIO_SID, self::TWILIO_TOKEN);

$twilio->messages->create(
    "whatsapp:+91".$phone_10,
    [
        "from" => "whatsapp:".$sender_raw,
        "body" => $ai_reply
    ]
);