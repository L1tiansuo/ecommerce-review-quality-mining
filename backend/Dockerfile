FROM maven:3.9.9-eclipse-temurin-17 AS build
WORKDIR /src
COPY docker/settings.xml /root/.m2/settings.xml
COPY pom.xml .
COPY src src
RUN mvn -B package -DskipTests
FROM eclipse-temurin:17-jre
WORKDIR /app
COPY --from=build /src/target/quality-review-1.0.0.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java","-Xmx768m","-jar","app.jar"]
