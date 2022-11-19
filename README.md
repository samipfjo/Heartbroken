# Heartbroken
 Keeps track of your disliked songs, albums, and artists on Spotify, and automatically skips them. Lives in your system tray.

**Currently only supports Windows**, but Linux and macOS support is planned.

![A heart icon inside of the Windows system try](https://user-images.githubusercontent.com/6316047/201472350-93581de4-41b1-4283-8b44-c4ca267b7d9b.png)
![The Heartbroken right-click menu expanded, showing the play/pause, dislike, un-dislike, show/hide console, and quit controls](https://user-images.githubusercontent.com/6316047/201472385-d8440ffb-95bf-4751-9a09-d6a7e71e2da7.png)


How this project protects your data:  
- All of your data is stored locally; neither the author nor anyone else will have access to it without you giving it to them. 
- The only external contact made by the app (other than to Spotify) is a call to the project's access token generator in the cloud and is completely unavoidable due to the nature of OAuth. The bare minimum amount of data is sent to facilitate that transaction - only the codes needed to generate the access token.
- Expanding on the above, there is zero tracking or analytics code included, and there will never be any. The author will fight to the death for your privacy.
