"use client";

import { useState, useEffect } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { FileText, Eye, Trash2, Shield } from "lucide-react";
import { complianceGroupsAPI, type ComplianceGroup } from "@/lib/api/compliance-groups";

interface UploadedDocument {
  id: number;
  title: string;
  checksum: string;
  blob_link: string;
  created_at: string;
  mime_type?: string;
  compliance_framework_id?: string;
}

interface DocumentTableProps {
  documents: UploadedDocument[];
  onView?: (document: UploadedDocument) => void;
  onDelete?: (document: UploadedDocument) => void;
  onComplianceFrameworkUpdate?: (documentId: number, complianceFrameworkId: string | null) => void;
  className?: string;
}

export function DocumentTable({ 
  documents, 
  onView, 
  onDelete,
  onComplianceFrameworkUpdate,
  className = "" 
}: DocumentTableProps) {
  const [complianceGroups, setComplianceGroups] = useState<ComplianceGroup[]>([]);
  const [isLoadingGroups, setIsLoadingGroups] = useState(true);
  const [updatingDocuments, setUpdatingDocuments] = useState<Set<number>>(new Set());

  useEffect(() => {
    fetchComplianceGroups();
  }, []);

  const fetchComplianceGroups = async () => {
    try {
      setIsLoadingGroups(true);
      const groups = await complianceGroupsAPI.getAllComplianceGroups();
      setComplianceGroups(groups);
    } catch (error) {
      console.error('Error fetching compliance groups:', error);
    } finally {
      setIsLoadingGroups(false);
    }
  };

  const handleComplianceFrameworkChange = async (documentId: number, complianceFrameworkId: string) => {
    setUpdatingDocuments(prev => new Set(prev).add(documentId));
    
    try {
      const finalId = complianceFrameworkId === '' ? null : complianceFrameworkId;
      await onComplianceFrameworkUpdate?.(documentId, finalId);
    } catch (error) {
      console.error('Error updating compliance framework:', error);
    } finally {
      setUpdatingDocuments(prev => {
        const newSet = new Set(prev);
        newSet.delete(documentId);
        return newSet;
      });
    }
  };
  if (documents.length === 0) {
    return null;
  }

  return (
    <div className={className}>
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Uploaded Documents</h2>
      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full table-fixed">
              <colgroup>
                <col className="w-[35%]" />
                <col className="w-[15%]" />
                <col className="w-[20%]" />
                <col className="w-[10%]" />
                <col className="w-[20%]" />
              </colgroup>
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Document
                  </th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Uploaded
                  </th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Compliance Group
                  </th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {documents.map((doc) => (
                  <tr key={doc.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <div className="flex items-center">
                        <FileText className="w-4 h-4 text-blue-600 mr-2 flex-shrink-0" />
                        <div className="min-w-0 flex-1">
                          <div className="text-sm font-medium text-gray-900 truncate" title={doc.title}>
                            {doc.title}
                          </div>
                          <div className="text-xs text-gray-500">ID: {doc.id}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-3 py-3">
                      <div className="text-xs text-gray-900">
                        {new Date(doc.created_at).toLocaleDateString()}
                      </div>
                      <div className="text-xs text-gray-500">
                        {new Date(doc.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </div>
                    </td>
                    <td className="px-3 py-3">
                      <div className="flex items-center">
                        <Shield className="w-3 h-3 text-blue-600 mr-1 flex-shrink-0" />
                        <select
                          value={doc.compliance_framework_id || ''}
                          onChange={(e) => handleComplianceFrameworkChange(doc.id, e.target.value)}
                          disabled={isLoadingGroups || updatingDocuments.has(doc.id)}
                          className="text-xs border border-gray-300 rounded px-1 py-1 bg-white focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed flex-1 min-w-0"
                        >
                          <option value="">None</option>
                          {complianceGroups.map((group) => (
                            <option key={group.id} value={group.id}>
                              {group.name}
                            </option>
                          ))}
                        </select>
                        {updatingDocuments.has(doc.id) && (
                          <div className="ml-1 w-3 h-3 border-2 border-blue-600 border-t-transparent rounded-full animate-spin flex-shrink-0"></div>
                        )}
                      </div>
                    </td>
                    <td className="px-3 py-3">
                      <span className="inline-flex px-2 py-1 text-xs font-semibold rounded-full bg-green-100 text-green-800">
                        Ready
                      </span>
                    </td>
                    <td className="px-3 py-3 text-right">
                      <div className="flex items-center justify-end space-x-1">
                        <Button 
                          variant="outline" 
                          size="sm"
                          onClick={() => onView?.(doc)}
                          className="p-1"
                        >
                          <Eye className="w-3 h-3" />
                        </Button>
                        <Button 
                          variant="outline" 
                          size="sm"
                          onClick={() => onDelete?.(doc)}
                          className="text-red-600 hover:text-red-700 hover:border-red-300 p-1"
                        >
                          <Trash2 className="w-3 h-3" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}