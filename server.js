const express = require("express");
const fetch = require("node-fetch");
const cors = require("cors");
const path = require("path");

const app = express();
app.use(cors());
app.use(express.json({ limit: "50mb" }));

// API route MUST be defined before the static file middleware
app.post("/api/claude", async (req, res) => {
  try {
    console.log("Received request, model:", req.body?.model);
    const response = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": process.env.ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01"
      },
      body: JSON.stringify(req.body),
      timeout: 120000
    });
    console.log("Anthropic status:", response.status);
    const data = await response.json();
    if (data.error) console.log("Anthropic error:", JSON.stringify(data.error));
    res.json(data);
  } catch (err) {
    console.log("Server error:", err.message);
    res.status(500).json({ error: { message: err.message } });
  }
});

// Static files AFTER the API route
app.use(express.static("public"));

// Catch-all LAST
app.get("*", (req, res) => {
  res.sendFile(path.join(__dirname, "public", "index.html"));
});

const PORT = process.env.PORT || 3000;
const server = app.listen(PORT, () => console.log(`Server running on port ${PORT}`));
server.timeout = 120000;
