"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { SegmentComplianceResult } from "@/lib/api/compliance-groups";
import { SegmentCard } from "./SegmentCard";

interface SegmentAnalysisListProps {
  segments: SegmentComplianceResult[];
}

export function SegmentAnalysisList({ segments }: SegmentAnalysisListProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Segment Analysis</CardTitle>
        <CardDescription>
          Detailed compliance analysis for each document segment
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-96">
          <div className="space-y-3">
            {segments.map((segment) => (
              <SegmentCard key={segment.segment_ordinal} segment={segment} />
            ))}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
}