# Heartbroken
 Keeps track of your disliked songs, albums, and artists on Spotify, and automatically skips them. Lives in your system tray.

**Currently only supports Windows**, but Linux and macOS support is planned.

----

![A heart icon inside of the Windows system try](https://user-images.githubusercontent.com/6316047/201472350-93581de4-41b1-4283-8b44-c4ca267b7d9b.png)
![The Heartbroken right-click menu expanded, showing the play/pause, dislike, un-dislike, show/hide console, and quit controls](https://user-images.githubusercontent.com/6316047/201472385-d8440ffb-95bf-4751-9a09-d6a7e71e2da7.png)

----

### How this project protects your data:

- All of your data is stored locally; neither the author nor anyone else will have access to it without you giving it to them. 
- The only external contact made by the app (other than to Spotify) is a call to the project's access token generator in the cloud and is completely unavoidable due to the nature of OAuth. The bare minimum amount of data is sent to facilitate that transaction - only the codes needed to generate the access token.
- Expanding on the above, there is zero tracking or analytics code included, and there will never be any. The author will fight to the death for your privacy.

----

### FAQ:

- Can you add this into the Spotify client itself?
  - Unfortunately, modifying the Spotify client is a _heavy_ violation of the Spotify Terms of Service. Doing so would risk getting peoples' accounts banned, and I'm not willing to do that for obvious reasons.

----

### Instructions for building from source

1) Create a new project on the Spotify developer hub 
1) Install Python >= v3.8
2) `pip install requirements-dev.txt`
3) Create a file called `secrets.json`, filling in your Spotify developer credentials: `{"client_id": "...", "token_url": "http(s)://...", "auth_key"=""}` (`auth_key` can be left empty)
4) `python setup.py build`  

If everything went well, the full built program will be at `./build/heartbroken_win/`

<br>

You will need to provide a server that responds to a request at `token_url` that can handle the following:

```
POST to <token_url>  
  Request:
    Type: json  
    Body: {"refresh_token": <string>, "auth_key": ""}

  <server requests access token from Spotify API>

  Response:
    Type: json
    Body: {"access_token": <string>, "expires_in": <int>}
```

Providing a local server for contributors to do testing with is on my to-do list.
