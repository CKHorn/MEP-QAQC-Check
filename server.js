const express = require("express");
const fetch = require("node-fetch");
const cors = require("cors");
const path = require("path");

const app = express();
app.use(cors());
app.use(express.json({ limit: "50mb" }));
app.use(express.static("public"));

app.post("/api/claude", async (req, res) => {
  // Set a long timeout so large PDFs don't get cut off
  req.setTimeout(300000); // 5 minutes
  res.setTimeout(300000);

  try {
    const response = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": process.env.ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01"
      },
      body: JSON.stringify(req.body),
      timeout: 280000 // 4m 40s — slightly under server timeout
    });

    const data = await response.json();
    if (data.error) {
      console.log("Anthropic error:", JSON.stringify(data.error));
    }
    res.json(data);
  } catch (err) {
    console.log("Server error:", err.message);
    if (err.type === "request-timeout") {
      res.status(504).json({ error: { message: "The request timed out. Try uploading a smaller PDF (fewer sheets) and run again." } });
    } else {
      res.status(500).json({ error: { message: err.message } });
    }
  }
});

app.get("*", (req, res) => {
  res.sendFile(path.join(__dirname, "public", "index.html"));
});

const PORT = process.env.PORT || 3000;
const server = app.listen(PORT, () => console.log(`Server running on port ${PORT}`));
server.timeout = 300000; // 5 minute server timeout
