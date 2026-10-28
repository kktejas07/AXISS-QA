import api from "./client";
import type { Scan, ScanConfig, Vulnerability, QAGap, TestCase, Report, ReportType, ReportFormat } from "../types";

export const createScan = (data: ScanConfig) =>
  api.post<Scan>("/scans", data);

export const getScans = () =>
  api.get<Scan[]>("/scans");

export const getScan = (id: string) =>
  api.get<Scan>(`/scans/${id}`);

export const getVulnerabilities = (scanId: string) =>
  api.get<Vulnerability[]>(`/scans/${scanId}/vulnerabilities`);

export const getQAGaps = (scanId: string) =>
  api.get<QAGap[]>(`/scans/${scanId}/gaps`);

export const getTestCases = (scanId: string) =>
  api.get<TestCase[]>(`/scans/${scanId}/test-cases`);

export const generateTestCases = (scanId: string) =>
  api.post<{ message: string }>(`/scans/${scanId}/test-cases/generate`);

export const getReports = (scanId: string) =>
  api.get<Report[]>(`/scans/${scanId}/reports`);

export const generateReport = (scanId: string, report_type: ReportType, format: ReportFormat) =>
  api.post<Report>(`/scans/${scanId}/reports`, { report_type, format });
