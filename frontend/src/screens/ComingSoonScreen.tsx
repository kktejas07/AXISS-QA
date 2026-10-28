import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
  useWindowDimensions,
} from "react-native";
import { StatusBar } from "expo-status-bar";
import { WaitlistForm } from "../components/WaitlistForm";
import { getHealth, getWaitlistCount } from "../lib/api";
import { colors, maxContentWidth, radius, spacing } from "../theme";

type ApiState = "checking" | "online" | "degraded" | "offline";

const STATUS_COPY: Record<ApiState, string> = {
  checking: "Connecting",
  online: "All systems go",
  degraded: "API up, database down",
  offline: "API offline",
};

const STATUS_COLOR: Record<ApiState, string> = {
  checking: colors.textDim,
  online: colors.accent,
  degraded: "#FBBF24",
  offline: colors.danger,
};

export function ComingSoonScreen() {
  const { width } = useWindowDimensions();
  const compact = width < 520;

  const [apiState, setApiState] = useState<ApiState>("checking");
  const [waitlistCount, setWaitlistCount] = useState<number | null>(null);

  const checkHealth = useCallback(async () => {
    try {
      const health = await getHealth();
      setApiState(health.db === "up" ? "online" : "degraded");
    } catch {
      setApiState("offline");
    }
  }, []);

  const loadCount = useCallback(async () => {
    try {
      const { count } = await getWaitlistCount();
      setWaitlistCount(count);
    } catch {
      setWaitlistCount(null);
    }
  }, []);

  useEffect(() => {
    checkHealth();
    loadCount();

    const interval = setInterval(checkHealth, 30_000);
    return () => clearInterval(interval);
  }, [checkHealth, loadCount]);

  const headlineSize = useMemo(() => (compact ? 38 : 58), [compact]);

  return (
    <View style={styles.root}>
      <StatusBar style="light" />

      <View style={styles.glowTop} pointerEvents="none" />
      <View style={styles.glowBottom} pointerEvents="none" />

      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.shell}>
          <View style={styles.header}>
            <View style={styles.logoMark}>
              <Text style={styles.logoMarkText}>A</Text>
            </View>
            <Text style={styles.wordmark}>
              AXISS<Text style={styles.wordmarkAccent}> QA</Text>
            </Text>
          </View>

          <View style={styles.hero}>
            <View style={styles.badge}>
              <View style={styles.badgeDot} />
              <Text style={styles.badgeText}>Coming soon</Text>
            </View>

            <Text style={[styles.title, { fontSize: headlineSize }]}>
              Quality assurance,{"\n"}
              <Text style={styles.titleAccent}>reimagined.</Text>
            </Text>

            <Text style={styles.subtitle}>
              Test smarter, ship faster. AXISS QA brings your test plans,
              executions and release confidence into one calm workspace.
            </Text>

            <View style={styles.formBlock}>
              <WaitlistForm onJoined={loadCount} />
            </View>

            {waitlistCount !== null && waitlistCount > 0 ? (
              <Text style={styles.socialProof}>
                {waitlistCount.toLocaleString()}{" "}
                {waitlistCount === 1 ? "person is" : "people are"} already
                waiting
              </Text>
            ) : null}
          </View>

          <View style={styles.footer}>
            <View style={styles.statusPill}>
              <View
                style={[
                  styles.statusDot,
                  { backgroundColor: STATUS_COLOR[apiState] },
                ]}
              />
              <Text style={styles.statusText}>{STATUS_COPY[apiState]}</Text>
            </View>

            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Refresh status"
              onPress={() => {
                setApiState("checking");
                checkHealth();
                loadCount();
              }}
              style={({ pressed }) => [pressed && styles.pressed]}
            >
              <Text style={styles.refreshText}>Refresh</Text>
            </Pressable>
          </View>
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: colors.background,
    overflow: "hidden",
  },
  glowTop: {
    position: "absolute",
    top: -220,
    right: -120,
    width: 520,
    height: 520,
    borderRadius: radius.pill,
    backgroundColor: "rgba(52, 211, 153, 0.12)",
  },
  glowBottom: {
    position: "absolute",
    bottom: -260,
    left: -160,
    width: 560,
    height: 560,
    borderRadius: radius.pill,
    backgroundColor: "rgba(56, 189, 248, 0.07)",
  },
  scrollContent: {
    flexGrow: 1,
    paddingVertical: spacing.xxl,
    paddingHorizontal: spacing.lg,
    justifyContent: "center",
    alignItems: "center",
  },
  shell: {
    width: "100%",
    maxWidth: maxContentWidth,
    minHeight: 520,
    justifyContent: "space-between",
    gap: spacing.xl,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  logoMark: {
    width: 30,
    height: 30,
    borderRadius: radius.sm,
    backgroundColor: colors.accent,
    alignItems: "center",
    justifyContent: "center",
  },
  logoMarkText: {
    color: colors.onAccent,
    fontSize: 16,
    fontWeight: "800",
  },
  wordmark: {
    color: colors.text,
    fontSize: 16,
    fontWeight: "700",
    letterSpacing: 2.4,
  },
  wordmarkAccent: {
    color: colors.accent,
  },
  hero: {
    gap: spacing.lg,
  },
  badge: {
    flexDirection: "row",
    alignItems: "center",
    alignSelf: "flex-start",
    gap: spacing.sm,
    paddingVertical: 6,
    paddingHorizontal: spacing.md,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: "rgba(52, 211, 153, 0.3)",
    backgroundColor: colors.accentSoft,
  },
  badgeDot: {
    width: 6,
    height: 6,
    borderRadius: radius.pill,
    backgroundColor: colors.accent,
  },
  badgeText: {
    color: colors.accent,
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 1.4,
    textTransform: "uppercase",
  },
  title: {
    color: colors.text,
    fontWeight: "800",
    letterSpacing: -1,
    lineHeight: Platform.OS === "web" ? undefined : 46,
  },
  titleAccent: {
    color: colors.accent,
  },
  subtitle: {
    color: colors.textMuted,
    fontSize: 16,
    lineHeight: 25,
    maxWidth: 500,
  },
  formBlock: {
    marginTop: spacing.sm,
  },
  socialProof: {
    color: colors.textDim,
    fontSize: 13,
  },
  footer: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    borderTopWidth: 1,
    borderTopColor: colors.border,
    paddingTop: spacing.md,
  },
  statusPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  statusDot: {
    width: 7,
    height: 7,
    borderRadius: radius.pill,
  },
  statusText: {
    color: colors.textDim,
    fontSize: 12,
    letterSpacing: 0.4,
  },
  refreshText: {
    color: colors.textMuted,
    fontSize: 12,
    fontWeight: "600",
  },
  pressed: {
    opacity: 0.7,
  },
});
