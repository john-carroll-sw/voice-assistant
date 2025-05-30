import { useState, useEffect } from "react";
import { SettingsIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";

interface SettingsProps {
    isMobile: boolean;
}

export default function Settings({ isMobile }: SettingsProps) {
    const [isDarkMode, setIsDarkMode] = useState(() => {
        return localStorage.getItem("isDarkMode") === "true";
    });

    useEffect(() => {
        localStorage.setItem("isDarkMode", isDarkMode.toString());
        if (isDarkMode) {
            document.documentElement.classList.add("dark");
        } else {
            document.documentElement.classList.remove("dark");
        }
    }, [isDarkMode]);

    const handleDarkModeChange = (checked: boolean) => {
        setIsDarkMode(checked);
    };

    const SettingsContent = () => (
        <div className="space-y-6">
            <div className="flex items-start justify-between">
                <div className="flex-1 space-y-0.5">
                    <Label htmlFor="dark-mode" className="text-gray-900 dark:text-gray-100">
                        Dark Mode
                    </Label>
                    <p className="text-sm text-gray-600 dark:text-gray-400">Toggle between light and dark theme</p>
                </div>
                <div className="ml-4 flex flex-col items-end">
                    <Switch id="dark-mode" checked={isDarkMode} onCheckedChange={handleDarkModeChange} aria-label="Toggle dark mode" />
                    <span className="text-xs text-gray-500 dark:text-gray-400">{isDarkMode ? "Dark Mode" : "Light Mode"}</span>
                </div>
            </div>
        </div>
    );

    if (isMobile) {
        return (
            <Sheet>
                <SheetTrigger asChild>
                    <Button variant="outline" size="icon">
                        <SettingsIcon className="h-[1.2rem] w-[1.2rem]" />
                        <span className="sr-only">Open settings</span>
                    </Button>
                </SheetTrigger>
                <SheetContent>
                    <SheetHeader>
                        <SheetTitle>Settings</SheetTitle>
                        <SheetDescription>Adjust your app preferences here.</SheetDescription>
                    </SheetHeader>
                    <SettingsContent />
                </SheetContent>
            </Sheet>
        );
    }

    return (
        <Dialog>
            <DialogTrigger asChild>
                <Button variant="outline" size="icon">
                    <SettingsIcon className="h-[1.2rem] w-[1.2rem]" />
                    <span className="sr-only">Open settings</span>
                </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-[425px]">
                <DialogHeader>
                    <DialogTitle>Settings</DialogTitle>
                    <DialogDescription>Adjust your app preferences here.</DialogDescription>
                </DialogHeader>
                <SettingsContent />
            </DialogContent>
        </Dialog>
    );
}
