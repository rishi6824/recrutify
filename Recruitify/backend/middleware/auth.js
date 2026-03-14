const ErrorHander = require("../utils/errorhander");
const catchAsyncErrors = require("./catchAsyncErrors");
const jwt = require("jsonwebtoken");
const User = require("../models/userModel");

exports.isAuthenticatedUser = catchAsyncErrors(async (req, res, next) => {
  const tokenCookie = req.cookies?.token;
  const refreshTokenCookie = req.cookies?.refresh_token;
  const authHeader = req.headers?.authorization;
  const tokenFromHeader =
    authHeader && authHeader.startsWith("Bearer ")
      ? authHeader.split(" ")[1]
      : null;
  // Prefer canonical cookie `token` to avoid identity mismatch with stale legacy cookies.
  // Fallback to refresh_token/header only when token cookie is not present.
  const tokenCandidates = tokenCookie
    ? [tokenCookie]
    : [refreshTokenCookie, tokenFromHeader].filter(Boolean);

  if (!tokenCandidates.length) {
    return next(new ErrorHander("Please Login to access this resource", 401));
  }

  let decodedData = null;
  for (const token of tokenCandidates) {
    try {
      decodedData = jwt.verify(token, process.env.JWT_SECRET);
      break;
    } catch (error) {
      // Try next candidate token (e.g. legacy refresh_token cookie)
    }
  }

  if (!decodedData) {
    return next(new ErrorHander("Json Web Token is invalid, Try again ", 400));
  }

  const user = await User.findById(decodedData.id);
  if (!user) {
    return next(new ErrorHander("User not found", 401));
  }

  req.user = user;
  next();
});

exports.authorizeRoles = (...roles) => {
  return (req, res, next) => {
    if (!roles.includes(req.user.role)) {
      return next(
        new ErrorHander(
          `Role: ${req.user.role} is not allowed to access this resouce `,
          403
        )
      );
    }

    next();
  };
};

exports.isAuthenticatedUserGraphQl = catchAsyncErrors(
  async (req, res, next) => {
    // Extract the Authorization header
    const authHeader = req.headers.authorization;

    if (!authHeader || !authHeader.startsWith("Bearer ")) {
      console.error(
        "Authorization header is missing or does not contain 'Bearer '"
      );
      return next(new ErrorHander("Please Login to access this resource", 401));
    }

    // Extract the token from the header
    const token = authHeader.split(" ")[1];

    try {
      // Verify the token
      const decodedData = jwt.verify(token, process.env.JWT_SECRET);

      // Attach the user to the request object
      req.user = await User.findById(decodedData.id);

      // Proceed to the next middleware or resolver
      next();
    } catch (error) {
      console.error("Token verification failed:", error);
      return next(new ErrorHander("Invalid token", 401));
    }
  }
);
