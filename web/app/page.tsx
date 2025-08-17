import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { MessageSquare, FileText, Bot, Zap, Upload } from "lucide-react";

export default function Home() {
  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 flex items-center justify-center">
        <div className="max-w-4xl mx-auto px-6">
          <div className="text-center mb-12">
            <h1 className="text-4xl font-bold text-gray-900 mb-4">
              Welcome to Amazon Product Guardian
            </h1>
            <p className="text-xl text-gray-600 mb-8">
              Your intelligent assistant for chat and document management
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-8">
            <Card className="hover:shadow-lg transition-shadow">
              <CardHeader>
                <CardTitle className="flex items-center">
                  <MessageSquare className="w-6 h-6 mr-2 text-blue-600" />
                  Chat with AI
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-gray-600 mb-4">
                  Start a conversation with our AI assistant. Ask questions, get help, or just chat about anything.
                </p>
                <Link href="/chat">
                  <Button className="w-full">
                    <Bot className="w-4 h-4 mr-2" />
                    Start Chatting
                  </Button>
                </Link>
              </CardContent>
            </Card>

            <Card className="hover:shadow-lg transition-shadow">
              <CardHeader>
                <CardTitle className="flex items-center">
                  <FileText className="w-6 h-6 mr-2 text-green-600" />
                  Document Management
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-gray-600 mb-4">
                  Upload and manage your documents. Our AI can help you analyze and work with your files.
                </p>
                <Link href="/documents">
                  <Button className="w-full">
                    <Upload className="w-4 h-4 mr-2" />
                    Manage Documents
                  </Button>
                </Link>
              </CardContent>
            </Card>
          </div>

          <div className="mt-12 text-center">
            <div className="inline-flex items-center space-x-2 text-gray-500">
              <Zap className="w-4 h-4" />
              <span>Powered by advanced AI technology</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
