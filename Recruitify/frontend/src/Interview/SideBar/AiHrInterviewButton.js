import React from "react";
import Button from "@mui/material/Button";
import { useLocation } from "react-router-dom";
import { useDispatch } from "react-redux";
import { openAlertMessage } from "../../store/actions/alertActions";
import { inviteCandidatesForInterview } from "../../store/slices/JobSlices";

const AiHrInterviewButton = () => {
  const location = useLocation();
  const dispatch = useDispatch();

  const goToAiInterview = async () => {
    const baseInterviewUrl =
      process.env.REACT_APP_AI_INTERVIEW_URL || "https://localhost:5000/interview_setup";

    const jobId = new URLSearchParams(location.search).get("jobId");
    const url = new URL(baseInterviewUrl);

    if (jobId) {
      url.searchParams.set("jobId", jobId);
    }

    if (!jobId) {
      dispatch(openAlertMessage("Job ID not found. Cannot send interview invites."));
      return;
    }

    const inviteResult = await dispatch(
      inviteCandidatesForInterview({
        formId: jobId,
        interviewLink: url.toString(),
      })
    );

    if (inviteResult.meta.requestStatus !== "fulfilled") {
      return;
    }

    const { invitedCount, totalCandidates, failed = [] } = inviteResult.payload || {};
    dispatch(
      openAlertMessage(
        failed.length > 0
          ? `Interview invites sent to ${invitedCount}/${totalCandidates} candidates.`
          : `Interview invites sent to ${invitedCount} candidates.`
      )
    );
  };

  return (
    <>
      <style>
        {`
          @keyframes bgColorChange {
            0% { background-color: #5865F2; } /* Starting color */
            50% { background-color: #FF5733; } /* Transition color */
            100% { background-color: #5865F2; } /* End with original color */
          }
        `}
      </style>
      <Button
        onClick={goToAiInterview}
        style={{
          width: "188px",
          height: "48px",
          borderRadius: "26px",
          margin: 0,
          padding: 0,
          minWidth: 0,
          marginTop: "10px",
          color: "white",
          backgroundColor: "#5865F2",
          animation: "bgColorChange 3s infinite", // Animation property
        }}
      >
        Take Hr Ai Interview
      </Button>
    </>
  );
};

export default AiHrInterviewButton;

