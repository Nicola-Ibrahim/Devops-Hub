FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src
COPY src/App.csproj ./
RUN dotnet restore App.csproj
COPY src/ ./
RUN dotnet publish App.csproj -c Release -o /out --no-restore
FROM mcr.microsoft.com/dotnet/aspnet:10.0
WORKDIR /app
COPY --from=build /out ./
ENV ASPNETCORE_URLS=http://+:8080
USER $APP_UID
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --retries=3 CMD bash -c '</dev/tcp/127.0.0.1/8080'
ENTRYPOINT ["dotnet", "App.dll"]
