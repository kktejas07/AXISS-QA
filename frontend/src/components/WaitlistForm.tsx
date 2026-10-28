import { useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
  useWindowDimensions,
} from "react-native";
import { joinWaitlist } from "../lib/api";
import { colors, radius, spacing } from "../theme";

type Status = "idle" | "submitting" | "success" | "error";

type Props = {
  onJoined?: () => void;
};

export function WaitlistForm({ onJoined }: Props) {
  const { width } = useWindowDimensions();
  const stacked = width < 460;

  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [message, setMessage] = useState("");

  const busy = status === "submitting";

  async function handleSubmit() {
    if (busy) return;

    const trimmed = email.trim();
    if (!trimmed) {
      setStatus("error");
      setMessage("Enter your email to join the waitlist.");
      return;
    }

    setStatus("submitting");
    setMessage("");

    try {
      const result = await joinWaitlist(trimmed);
      setStatus("success");
      setMessage(result.message);
      onJoined?.();
    } catch (error) {
      setStatus("error");
      setMessage(
        error instanceof Error
          ? error.message
          : "Could not reach the server. Please try again.",
      );
    }
  }

  if (status === "success") {
    return (
      <View style={styles.successCard} accessibilityLiveRegion="polite">
        <View style={styles.successIcon}>
          <Text style={styles.successIconText}>✓</Text>
        </View>
        <View style={styles.successCopy}>
          <Text style={styles.successTitle}>You&apos;re on the list</Text>
          <Text style={styles.successMessage}>{message}</Text>
        </View>
        <Pressable
          accessibilityRole="button"
          onPress={() => {
            setEmail("");
            setStatus("idle");
            setMessage("");
          }}
          style={({ pressed }) => [
            styles.ghostButton,
            pressed && styles.pressed,
          ]}
        >
          <Text style={styles.ghostButtonText}>Add another</Text>
        </Pressable>
      </View>
    );
  }

  return (
    <View style={styles.wrapper}>
      <View style={[styles.row, stacked && styles.rowStacked]}>
        <TextInput
          value={email}
          onChangeText={(value) => {
            setEmail(value);
            if (status === "error") {
              setStatus("idle");
              setMessage("");
            }
          }}
          onSubmitEditing={handleSubmit}
          placeholder="you@company.com"
          placeholderTextColor={colors.textDim}
          autoCapitalize="none"
          autoCorrect={false}
          autoComplete="email"
          keyboardType="email-address"
          inputMode="email"
          returnKeyType="send"
          editable={!busy}
          accessibilityLabel="Email address"
          style={styles.input}
        />

        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Join the waitlist"
          disabled={busy}
          onPress={handleSubmit}
          style={({ pressed }) => [
            styles.button,
            stacked && styles.buttonStacked,
            (pressed || busy) && styles.pressed,
          ]}
        >
          {busy ? (
            <ActivityIndicator color={colors.onAccent} size="small" />
          ) : (
            <Text style={styles.buttonText}>Notify me</Text>
          )}
        </Pressable>
      </View>

      {message ? (
        <View
          style={[
            styles.messageRow,
            status === "error" ? styles.messageRowError : undefined,
          ]}
          accessibilityLiveRegion="polite"
        >
          <Text
            style={[
              styles.message,
              status === "error" ? styles.messageError : undefined,
            ]}
          >
            {message}
          </Text>
        </View>
      ) : (
        <Text style={styles.hint}>
          Early access invites go out first. No spam, ever.
        </Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: {
    width: "100%",
    gap: spacing.sm,
  },
  row: {
    flexDirection: "row",
    gap: spacing.sm,
    width: "100%",
  },
  rowStacked: {
    flexDirection: "column",
  },
  input: {
    flex: 1,
    minHeight: 52,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    paddingHorizontal: spacing.md,
    color: colors.text,
    fontSize: 16,
  },
  button: {
    minHeight: 52,
    paddingHorizontal: spacing.lg,
    borderRadius: radius.md,
    backgroundColor: colors.accent,
    alignItems: "center",
    justifyContent: "center",
  },
  buttonStacked: {
    width: "100%",
  },
  buttonText: {
    color: colors.onAccent,
    fontSize: 16,
    fontWeight: "700",
    letterSpacing: 0.2,
  },
  pressed: {
    opacity: 0.75,
  },
  hint: {
    color: colors.textDim,
    fontSize: 13,
    paddingHorizontal: spacing.xs,
  },
  messageRow: {
    borderRadius: radius.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
  },
  messageRowError: {
    backgroundColor: colors.dangerSoft,
  },
  message: {
    color: colors.textMuted,
    fontSize: 13,
  },
  messageError: {
    color: colors.danger,
  },
  successCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    width: "100%",
    padding: spacing.md,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: "rgba(52, 211, 153, 0.35)",
    backgroundColor: colors.accentSoft,
  },
  successIcon: {
    width: 36,
    height: 36,
    borderRadius: radius.pill,
    backgroundColor: colors.accent,
    alignItems: "center",
    justifyContent: "center",
  },
  successIconText: {
    color: colors.onAccent,
    fontSize: 18,
    fontWeight: "800",
  },
  successCopy: {
    flex: 1,
    gap: 2,
  },
  successTitle: {
    color: colors.text,
    fontSize: 15,
    fontWeight: "700",
  },
  successMessage: {
    color: colors.textMuted,
    fontSize: 13,
  },
  ghostButton: {
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: radius.sm,
  },
  ghostButtonText: {
    color: colors.accent,
    fontSize: 13,
    fontWeight: "600",
  },
});
