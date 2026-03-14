const nodeMailer = require("nodemailer");

const sendEmail = async (options) => {
  const host = process.env.SMTP_HOST || process.env.SMPT_HOST;
  const port = Number(process.env.SMTP_PORT || process.env.SMPT_PORT || 587);
  const service = process.env.SMTP_SERVICE || process.env.SMPT_SERVICE;
  const user = process.env.SMTP_MAIL || process.env.SMPT_MAIL;
  const pass = process.env.SMTP_PASSWORD || process.env.SMPT_PASSWORD;

  if (!host && !service) {
    throw new Error("SMTP host/service is not configured");
  }

  if (!user || !pass) {
    throw new Error("SMTP credentials are not configured");
  }

  const transporter = nodeMailer.createTransport({
    host,
    port,
    secure: port === 465,
    service,
    auth: {
      user,
      pass,
    },
  });

  const to = String(options.to || options.mail || "").trim();
  const from = String(process.env.EMAIL_FROM || user || "").trim();

  if (!to) {
    throw new Error("Recipient email is missing");
  }

  if (!from || from.includes("<YOUR_EMAIL>")) {
    throw new Error(
      "EMAIL_FROM is invalid. Set a real sender email (and verify it in your SMTP provider)."
    );
  }

  const mailOptions = {
    from,
    to,
    subject: options.subject,
    text: options.text || "",
    html: options.html,
  };

  console.info("[Email] Sending email", {
    host,
    from: mailOptions.from,
    to: mailOptions.to,
    subject: mailOptions.subject,
  });

  try {
    const info = await transporter.sendMail(mailOptions);

    console.info("[Email] Email sent successfully", {
      to: mailOptions.to,
      subject: mailOptions.subject,
      messageId: info?.messageId,
      accepted: info?.accepted,
      rejected: info?.rejected,
      response: info?.response,
    });

    return info;
  } catch (error) {
    console.error("[Email] Failed to send email", {
      host,
      from: mailOptions.from,
      to: mailOptions.to,
      subject: mailOptions.subject,
      code: error?.code,
      command: error?.command,
      response: error?.response,
      responseCode: error?.responseCode,
      message: error?.message,
    });

    throw new Error(
      `Failed to send email to ${mailOptions.to}: ${
        error?.response || error?.message || "Unknown SMTP error"
      }`
    );
  }
};

module.exports = sendEmail;

