"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Shield, Calendar, ArrowLeft, FileText, Settings, Edit2, Save, X, AlertCircle } from "lucide-react";
import { complianceGroupsAPI, type ComplianceGroup, type ComplianceGroupDocument } from "@/lib/api/compliance-groups";
import { DocumentAnalysis } from "@/components/analysis/DocumentAnalysis";

export default function ComplianceGroupDetailPage() {
  const params = useParams();
  const router = useRouter();
  const groupId = params.id as string;
  
  const [group, setGroup] = useState<ComplianceGroup | null>(null);
  const [documents, setDocuments] = useState<ComplianceGroupDocument[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingDocuments, setIsLoadingDocuments] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [editForm, setEditForm] = useState({
    name: "",
    description: "",
  });

  useEffect(() => {
    if (groupId) {
      fetchGroup();
      fetchDocuments();
    }
  }, [groupId]);

  const fetchGroup = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const fetchedGroup = await complianceGroupsAPI.getComplianceGroup(groupId);
      setGroup(fetchedGroup);
      setEditForm({
        name: fetchedGroup.name,
        description: fetchedGroup.description || "",
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch compliance group');
      console.error('Error fetching compliance group:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchDocuments = async () => {
    try {
      setIsLoadingDocuments(true);
      const response = await complianceGroupsAPI.getComplianceGroupDocuments(groupId);
      setDocuments(response.documents);
    } catch (err) {
      console.error('Error fetching compliance group documents:', err);
      // Don't set main error state for documents, just log it
    } finally {
      setIsLoadingDocuments(false);
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "long",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const handleEdit = () => {
    setIsEditing(true);
    setError(null);
  };

  const handleCancel = () => {
    setIsEditing(false);
    setError(null);
    // Reset form to original values
    if (group) {
      setEditForm({
        name: group.name,
        description: group.description || "",
      });
    }
  };

  const handleSave = async () => {
    if (!editForm.name.trim()) {
      setError("Name is required");
      return;
    }

    setIsSaving(true);
    setError(null);

    try {
      await complianceGroupsAPI.updateComplianceGroup(groupId, {
        name: editForm.name.trim(),
        description: editForm.description.trim() || undefined,
      });

      // Refresh the data
      await fetchGroup();
      setIsEditing(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update compliance group');
      console.error('Error updating compliance group:', err);
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <Shield className="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600">Loading compliance group details...</p>
        </div>
      </div>
    );
  }

  if (error || !group) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <Shield className="h-12 w-12 text-red-400 mx-auto mb-4" />
          <h2 className="text-lg font-semibold text-gray-900 mb-2">
            {error ? "Error Loading Group" : "Group Not Found"}
          </h2>
          <p className="text-gray-600 mb-4">
            {error || "The compliance group you're looking for doesn't exist."}
          </p>
          <Button onClick={() => router.push('/compliance-groups')} variant="outline">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Compliance Groups
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="border-b border-gray-200 bg-white px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => router.push('/compliance-groups')}
              className="mr-4"
            >
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back
            </Button>
            <div>
              <h1 className="text-2xl font-semibold text-gray-900 flex items-center">
                <Shield className="h-6 w-6 mr-2 text-blue-600" />
                {group.name}
              </h1>
              <p className="text-sm text-gray-600 mt-1">
                Compliance group details and management
              </p>
            </div>
          </div>
          <div className="flex items-center space-x-3">
            {isEditing ? (
              <>
                <Button 
                  variant="outline" 
                  size="sm"
                  onClick={handleCancel}
                  disabled={isSaving}
                >
                  <X className="h-4 w-4 mr-2" />
                  Cancel
                </Button>
                <Button 
                  size="sm"
                  onClick={handleSave}
                  disabled={isSaving || !editForm.name.trim()}
                >
                  <Save className="h-4 w-4 mr-2" />
                  {isSaving ? "Saving..." : "Save"}
                </Button>
              </>
            ) : (
              <Button 
                variant="outline" 
                size="sm"
                onClick={handleEdit}
              >
                <Edit2 className="h-4 w-4 mr-2" />
                Edit Group
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-6">
        <div className="max-w-4xl mx-auto space-y-6">
          {/* Error Display */}
          {error && (
            <Card className="border-red-200 bg-red-50">
              <CardContent className="p-4">
                <div className="flex items-center">
                  <AlertCircle className="h-5 w-5 text-red-600 mr-3" />
                  <div>
                    <h3 className="text-sm font-medium text-red-800">Error</h3>
                    <p className="text-sm text-red-700 mt-1">{error}</p>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setError(null)}
                    className="ml-auto text-red-600 border-red-300 hover:bg-red-100"
                  >
                    Dismiss
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}
          {/* Overview Card */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Shield className="h-5 w-5 mr-2 text-blue-600" />
                Overview
              </CardTitle>
              <CardDescription>
                Basic information about this compliance group
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="md:col-span-2">
                  <label className="text-sm font-medium text-gray-700">Name</label>
                  {isEditing ? (
                    <Input
                      value={editForm.name}
                      onChange={(e) => setEditForm(prev => ({ ...prev, name: e.target.value }))}
                      placeholder="Enter compliance group name"
                      className="mt-1"
                      disabled={isSaving}
                    />
                  ) : (
                    <p className="mt-1 text-sm text-gray-900">{group.name}</p>
                  )}
                </div>
                <div className="md:col-span-2">
                  <label className="text-sm font-medium text-gray-700">Description</label>
                  {isEditing ? (
                    <Textarea
                      value={editForm.description}
                      onChange={(e) => setEditForm(prev => ({ ...prev, description: e.target.value }))}
                      placeholder="Enter description (optional)"
                      className="mt-1"
                      disabled={isSaving}
                    />
                  ) : (
                    <p className="mt-1 text-sm text-gray-900">
                      {group.description || "No description provided"}
                    </p>
                  )}
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700">Created</label>
                  <div className="mt-1 flex items-center text-sm text-gray-900">
                    <Calendar className="h-4 w-4 mr-2 text-gray-400" />
                    {formatDate(group.created_at)}
                  </div>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700">Last Updated</label>
                  <div className="mt-1 flex items-center text-sm text-gray-900">
                    <Calendar className="h-4 w-4 mr-2 text-gray-400" />
                    {formatDate(group.updated_at)}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Associated Documents Card */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <div className="flex items-center">
                  <FileText className="h-5 w-5 mr-2 text-blue-600" />
                  Associated Documents
                  <Badge variant="secondary" className="ml-2">
                    {documents.length}
                  </Badge>
                </div>
                <Button 
                  variant="outline" 
                  size="sm"
                  onClick={() => router.push('/documents')}
                >
                  Manage Documents
                </Button>
              </CardTitle>
              <CardDescription>
                Documents that are assigned to this compliance group
              </CardDescription>
            </CardHeader>
            <CardContent>
              {isLoadingDocuments ? (
                <div className="text-center py-8">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
                  <p className="text-gray-600">Loading documents...</p>
                </div>
              ) : documents.length === 0 ? (
                <div className="text-center py-8">
                  <FileText className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-gray-900 mb-2">No Documents Assigned</h3>
                  <p className="text-gray-600 mb-4">
                    No documents are currently assigned to this compliance group
                  </p>
                  <Button variant="outline" onClick={() => router.push('/documents')}>
                    Assign Documents
                  </Button>
                </div>
              ) : (
                <div className="space-y-3">
                  {documents.map((doc) => (
                    <div 
                      key={doc.id} 
                      className="flex items-center justify-between p-3 border border-gray-200 rounded-lg hover:bg-gray-50"
                    >
                      <div className="flex items-center flex-1 min-w-0">
                        <FileText className="h-4 w-4 text-blue-600 mr-3 flex-shrink-0" />
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-medium text-gray-900 truncate" title={doc.title}>
                            {doc.title}
                          </p>
                          <p className="text-xs text-gray-500">
                            ID: {doc.id} • {formatDate(doc.created_at)}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center space-x-2 ml-4">
                        <Button 
                          variant="outline" 
                          size="sm"
                          onClick={() => router.push(`/documents/${doc.id}`)}
                        >
                          View
                        </Button>
                        <Button 
                          variant="outline" 
                          size="sm"
                          onClick={() => window.open(doc.blob_link, '_blank')}
                        >
                          Download
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Run Analysis Section */}
          <DocumentAnalysis 
            frameworkId={groupId} 
            frameworkName={group.name} 
          />

        </div>
      </div>
    </div>
  );
}
